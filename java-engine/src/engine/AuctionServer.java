package engine;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;

import java.io.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;

/**
 * AuctionServer exposes the Java Auction Engine over HTTP so that
 * the Python Flask backend can communicate with it.
 * 
 * Communication flow:
 *   Browser -> Flask (Python) -> AuctionServer (Java) -> AuctionManager -> PriorityQueue
 * 
 * This uses Java's built-in com.sun.net.httpserver.HttpServer (no external libraries needed).
 * 
 * Endpoints:
 *   POST /load-auction               — Register an auction in the engine
 *   POST /place-bid                   — Validate and place a bid
 *   GET  /auction-status?id=X         — Get auction status and highest bid
 *   POST /simulate-concurrent-bids    — Run concurrent bidding simulation (Phase 3)
 *   GET  /health                      — Check if Java engine is running
 */
public class AuctionServer {
    private HttpServer server;
    private AuctionManager manager;
    private int port;

    public AuctionServer(int port) {
        this.port = port;
        this.manager = new AuctionManager();
    }

    public AuctionManager getManager() {
        return manager;
    }

    public void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress(port), 0);

        server.createContext("/health", new HealthHandler());
        server.createContext("/load-auction", new LoadAuctionHandler());
        server.createContext("/remove-auction", new RemoveAuctionHandler());
        server.createContext("/place-bid", new PlaceBidHandler());
        server.createContext("/auction-status", new AuctionStatusHandler());
        server.createContext("/get-bids", new GetBidsHandler());
        server.createContext("/simulate-concurrent-bids", new SimulateConcurrentBidsHandler());

        // Bug Fix #11: Use a thread pool so multiple HTTP requests (from Flask)
        // can be received and queued concurrently. The ReentrantLock in
        // AuctionManager still serializes the critical section.
        server.setExecutor(Executors.newFixedThreadPool(10));
        server.start();
        System.out.println("Java Auction Engine running on port " + port);
    }

    public void stop() {
        if (server != null) {
            server.stop(0);
        }
    }

    // ========================
    // HTTP Handlers
    // ========================

    /**
     * GET /health
     */
    class HealthHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }
            sendResponse(exchange, 200, "{\"status\":\"ok\",\"engine\":\"java-auction-engine\"}");
        }
    }

    /**
     * POST /load-auction
     */
    class LoadAuctionHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String body = readBody(exchange);

            try {
                int id = getIntValue(body, "id");
                String title = getStringValue(body, "title");
                String description = getStringValue(body, "description");
                double startingPrice = getDoubleValue(body, "startingPrice");
                double minimumIncrement = getDoubleValue(body, "minimumIncrement");
                double currentHighestBid = getDoubleValue(body, "currentHighestBid");
                long startTime = getLongValue(body, "startTime");
                long endTime = getLongValue(body, "endTime");

                Auction auction = new Auction(id, title, description, startingPrice,
                        minimumIncrement, startTime, endTime);

                // Reconstruct PriorityQueue from restored bids
                List<Bid> existingBids = parseBidsArray(body, id);
                for (Bid b : existingBids) {
                    auction.getBidQueue().addBid(b);
                }

                if (auction.getBidQueue().getHighestBid() != null) {
                    auction.setCurrentHighestBid(auction.getBidQueue().getHighestBid().getAmount());
                } else {
                    auction.setCurrentHighestBid(currentHighestBid);
                }

                manager.loadAuction(auction);

                sendResponse(exchange, 200,
                    "{\"success\":true,\"message\":\"Auction loaded in engine (" + existingBids.size() + " bids restored)\"}");
            } catch (Exception e) {
                sendResponse(exchange, 400,
                    "{\"success\":false,\"message\":\"Invalid auction data: " + escapeJson(e.getMessage()) + "\"}");
            }
        }
    }

    /**
     * POST /remove-auction
     */
    class RemoveAuctionHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String body = readBody(exchange);

            try {
                int id = getIntValue(body, "id");
                manager.removeAuction(id);

                sendResponse(exchange, 200, "{\"success\":true,\"message\":\"Auction removed from engine\"}");
            } catch (Exception e) {
                sendResponse(exchange, 400, "{\"success\":false,\"message\":\"Invalid request data\"}");
            }
        }
    }

    /**
     * POST /place-bid
     */
    class PlaceBidHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String body = readBody(exchange);

            try {
                int auctionId = getIntValue(body, "auctionId");
                String bidderName = getStringValue(body, "bidderName");
                double amount = getDoubleValue(body, "amount");

                AuctionManager.BidResult result = manager.placeBid(auctionId, bidderName, amount);

                String json = "{\"success\":" + result.success +
                              ",\"message\":\"" + escapeJson(result.message) + "\"" +
                              ",\"highestBid\":" + result.highestBid + "}";

                int statusCode = result.success ? 200 : 400;
                sendResponse(exchange, statusCode, json);
            } catch (Exception e) {
                sendResponse(exchange, 400,
                    "{\"success\":false,\"message\":\"Invalid bid data: " + escapeJson(e.getMessage()) + "\"}");
            }
        }
    }

    /**
     * GET /auction-status?id=1
     */
    class AuctionStatusHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String query = exchange.getRequestURI().getQuery();
            if (query == null || !query.contains("id=")) {
                sendResponse(exchange, 400, "{\"error\":\"Missing auction id\"}");
                return;
            }

            try {
                int auctionId = Integer.parseInt(query.split("id=")[1].split("&")[0]);
                Auction auction = manager.getAuction(auctionId);

                if (auction == null) {
                    sendResponse(exchange, 404, "{\"error\":\"Auction not found in engine\"}");
                    return;
                }

                auction.updateStatus();

                String json = "{\"id\":" + auction.getId() +
                              ",\"status\":\"" + auction.getStatus() + "\"" +
                              ",\"currentHighestBid\":" + auction.getCurrentHighestBid() +
                              ",\"minimumNextBid\":" + auction.getMinimumNextBid() +
                              ",\"totalBids\":" + auction.getBidQueue().size() + "}";

                sendResponse(exchange, 200, json);
            } catch (NumberFormatException e) {
                sendResponse(exchange, 400, "{\"error\":\"Invalid auction id\"}");
            }
        }
    }

    /**
     * GET /get-bids?id=1
     * Returns the PriorityQueue elements sorted from highest priority (highest bid) to lowest.
     */
    class GetBidsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String query = exchange.getRequestURI().getQuery();
            if (query == null || !query.contains("id=")) {
                sendResponse(exchange, 400, "{\"error\":\"Missing auction id\"}");
                return;
            }

            try {
                int auctionId = Integer.parseInt(query.split("id=")[1].split("&")[0]);
                List<Bid> bids = manager.getBids(auctionId);

                if (bids == null) {
                    sendResponse(exchange, 404, "{\"error\":\"Auction not found in engine\"}");
                    return;
                }

                StringBuilder json = new StringBuilder();
                json.append("{\"success\":true,\"auctionId\":").append(auctionId)
                    .append(",\"totalBids\":").append(bids.size())
                    .append(",\"queue\":[");

                for (int i = 0; i < bids.size(); i++) {
                    Bid b = bids.get(i);
                    if (i > 0) json.append(",");
                    json.append("{\"bidderName\":\"").append(escapeJson(b.getBidderName())).append("\"")
                        .append(",\"amount\":").append(b.getAmount())
                        .append(",\"timestamp\":").append(b.getTimestamp()).append("}");
                }
                json.append("]}");

                sendResponse(exchange, 200, json.toString());
            } catch (NumberFormatException e) {
                sendResponse(exchange, 400, "{\"error\":\"Invalid auction id\"}");
            }
        }
    }

    /**
     * POST /simulate-concurrent-bids
     * 
     * Runs a concurrent bidding simulation using multiple Java threads.
     * Called by Flask when the user triggers the concurrency demo from the frontend.
     * 
     * Expected JSON body:
     * {"auctionId":1,"bidders":[{"name":"Bidder-1","amount":10500},{"name":"Bidder-2","amount":11000}]}
     * 
     * Returns JSON with results for each bidder and the final highest bid.
     */
    class SimulateConcurrentBidsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"POST".equals(exchange.getRequestMethod())) {
                sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
                return;
            }

            String body = readBody(exchange);

            try {
                int auctionId = getIntValue(body, "auctionId");

                // Parse the bidders array from JSON manually
                List<ConcurrentBidSimulation.BidderEntry> bidders = parseBiddersArray(body);

                if (bidders.isEmpty()) {
                    sendResponse(exchange, 400,
                        "{\"success\":false,\"message\":\"No bidders provided\"}");
                    return;
                }

                // Run the simulation with real concurrent threads
                List<ConcurrentBidSimulation.SimulationResult> results =
                    ConcurrentBidSimulation.runSimulation(manager, auctionId, bidders);

                // Get the final highest bid
                Auction auction = manager.getAuction(auctionId);
                double finalHighest = (auction != null) ? auction.getCurrentHighestBid() : 0;

                // Build JSON response
                StringBuilder json = new StringBuilder();
                json.append("{\"success\":true,\"results\":[");

                for (int i = 0; i < results.size(); i++) {
                    ConcurrentBidSimulation.SimulationResult r = results.get(i);
                    if (i > 0) json.append(",");
                    json.append("{\"bidder\":\"").append(escapeJson(r.bidder)).append("\"")
                        .append(",\"amount\":").append(r.amount)
                        .append(",\"status\":\"").append(r.status).append("\"")
                        .append(",\"message\":\"").append(escapeJson(r.message)).append("\"}");
                }

                json.append("],\"highestBid\":").append(finalHighest).append("}");

                sendResponse(exchange, 200, json.toString());

            } catch (Exception e) {
                sendResponse(exchange, 400,
                    "{\"success\":false,\"message\":\"Simulation error: " + escapeJson(e.getMessage()) + "\"}");
            }
        }
    }

    // ========================
    // Utility Methods
    // ========================

    private void sendResponse(HttpExchange exchange, int statusCode, String response) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        byte[] bytes = response.getBytes(StandardCharsets.UTF_8);
        exchange.sendResponseHeaders(statusCode, bytes.length);
        OutputStream os = exchange.getResponseBody();
        os.write(bytes);
        os.close();
    }

    private String readBody(HttpExchange exchange) throws IOException {
        InputStream is = exchange.getRequestBody();
        BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line);
        }
        reader.close();
        return sb.toString();
    }

    private String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    // Simple JSON parsing helpers

    private int findKeyIndex(String json, String key) {
        String search = "\"" + key + "\"";
        int idx = 0;
        while ((idx = json.indexOf(search, idx)) != -1) {
            if (idx == 0 || json.charAt(idx - 1) == '{' || json.charAt(idx - 1) == ',' || json.charAt(idx - 1) == ' ' || json.charAt(idx - 1) == '\t' || json.charAt(idx - 1) == '\n') {
                int afterQuote = idx + search.length();
                while (afterQuote < json.length() && (json.charAt(afterQuote) == ' ' || json.charAt(afterQuote) == '\t' || json.charAt(afterQuote) == '\n')) {
                    afterQuote++;
                }
                if (afterQuote < json.length() && json.charAt(afterQuote) == ':') {
                    return idx;
                }
            }
            idx += search.length();
        }
        return -1;
    }

    private String getStringValue(String json, String key) {
        int keyIdx = findKeyIndex(json, key);
        if (keyIdx == -1) return "";
        int colonIdx = json.indexOf(":", keyIdx + key.length() + 2);
        if (colonIdx == -1) return "";
        int startQuote = json.indexOf("\"", colonIdx + 1);
        if (startQuote == -1) return "";
        int endQuote = json.indexOf("\"", startQuote + 1);
        if (endQuote == -1) return "";
        return json.substring(startQuote + 1, endQuote);
    }

    private int getIntValue(String json, String key) {
        return (int) getDoubleValue(json, key);
    }

    private long getLongValue(String json, String key) {
        return (long) getDoubleValue(json, key);
    }

    private double getDoubleValue(String json, String key) {
        int keyIdx = findKeyIndex(json, key);
        if (keyIdx == -1) throw new RuntimeException("Missing field: " + key);
        int colonIdx = json.indexOf(":", keyIdx + key.length() + 2);
        if (colonIdx == -1) throw new RuntimeException("Missing colon for field: " + key);
        int start = colonIdx + 1;
        while (start < json.length() && (Character.isWhitespace(json.charAt(start)) || json.charAt(start) == '"')) {
            start++;
        }
        int end = start;
        while (end < json.length() && (Character.isDigit(json.charAt(end)) || json.charAt(end) == '.' || json.charAt(end) == '-')) {
            end++;
        }
        return Double.parseDouble(json.substring(start, end));
    }

    /**
     * Parse the "bidders" array from the JSON body.
     * Expected format: "bidders":[{"name":"X","amount":123},...]
     * 
     * Bug Fix #10: Uses a character-by-character approach to correctly handle
     * names with spaces, special chars, or any valid JSON string content.
     */
    private List<ConcurrentBidSimulation.BidderEntry> parseBiddersArray(String json) {
        List<ConcurrentBidSimulation.BidderEntry> bidders = new ArrayList<>();

        // Find the "bidders": key and then its array
        int bidderKeyIdx = json.indexOf("\"bidders\"");
        if (bidderKeyIdx == -1) return bidders;

        int arrStart = json.indexOf("[", bidderKeyIdx);
        if (arrStart == -1) return bidders;

        // Find the matching closing bracket by counting depth
        int depth = 0;
        int arrEnd = -1;
        for (int i = arrStart; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == '[') depth++;
            else if (c == ']') {
                depth--;
                if (depth == 0) {
                    arrEnd = i;
                    break;
                }
            }
        }
        if (arrEnd == -1) return bidders;

        String arrContent = json.substring(arrStart + 1, arrEnd).trim();
        if (arrContent.isEmpty()) return bidders;

        // Split individual objects by tracking brace depth
        int objDepth = 0;
        int objStart = -1;
        for (int i = 0; i < arrContent.length(); i++) {
            char c = arrContent.charAt(i);
            if (c == '{') {
                if (objDepth == 0) objStart = i;
                objDepth++;
            } else if (c == '}') {
                objDepth--;
                if (objDepth == 0 && objStart >= 0) {
                    String obj = arrContent.substring(objStart, i + 1);
                    try {
                        String name = getStringValue(obj, "name");
                        double amount = getDoubleValue(obj, "amount");
                        if (!name.isEmpty() && amount > 0) {
                            bidders.add(new ConcurrentBidSimulation.BidderEntry(name, amount));
                        }
                    } catch (Exception e) {
                        System.err.println("Skipping malformed bidder entry: " + obj);
                    }
                    objStart = -1;
                }
            }
        }

        return bidders;
    }

    /**
     * Parse the "bids" array from the JSON body.
     * Expected format: "bids":[{"id":1,"bidderName":"Alice","amount":10000.0,"timestamp":1700000000000},...]
     */
    private List<Bid> parseBidsArray(String json, int defaultAuctionId) {
        List<Bid> bids = new ArrayList<>();
        int keyIdx = json.indexOf("\"bids\"");
        if (keyIdx == -1) return bids;

        int arrStart = json.indexOf("[", keyIdx);
        if (arrStart == -1) return bids;

        int depth = 0;
        int arrEnd = -1;
        for (int i = arrStart; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == '[') depth++;
            else if (c == ']') {
                depth--;
                if (depth == 0) {
                    arrEnd = i;
                    break;
                }
            }
        }
        if (arrEnd == -1) return bids;

        String arrContent = json.substring(arrStart + 1, arrEnd).trim();
        if (arrContent.isEmpty()) return bids;

        int objDepth = 0;
        int objStart = -1;
        for (int i = 0; i < arrContent.length(); i++) {
            char c = arrContent.charAt(i);
            if (c == '{') {
                if (objDepth == 0) objStart = i;
                objDepth++;
            } else if (c == '}') {
                objDepth--;
                if (objDepth == 0 && objStart >= 0) {
                    String obj = arrContent.substring(objStart, i + 1);
                    try {
                        int bidId = getIntValue(obj, "id");
                        String bidderName = getStringValue(obj, "bidderName");
                        double amount = getDoubleValue(obj, "amount");
                        long timestamp = getLongValue(obj, "timestamp");
                        if (!bidderName.isEmpty() && amount > 0) {
                            bids.add(new Bid(bidId, defaultAuctionId, bidderName, amount, timestamp));
                        }
                    } catch (Exception e) {
                        System.err.println("Skipping malformed bid entry: " + obj);
                    }
                    objStart = -1;
                }
            }
        }

        return bids;
    }
}
