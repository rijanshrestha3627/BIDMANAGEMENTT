# Final Project Report: University Auction Bid Management System

## 1. Project Overview
The University Auction Bid Management System is a multi-tier web application designed to facilitate secure, real-time, competitive bidding on items listed within a university campus context. It bridges the gap between frontend web interfaces, a Python-based REST API, and a highly concurrent Java-based auction engine.

## 2. Problem Statement
Managing live, concurrent bids from multiple users requires robust data structures to instantly determine the highest bidder and strict concurrency controls to prevent race conditions. Traditional single-threaded applications struggle with real-time auction integrity.

## 3. Objectives
- Implement a secure user and admin authentication system.
- Build a responsive, user-friendly frontend interface.
- Manage persistent data using a relational database (SQLite).
- Offload critical, high-frequency bid processing to a high-performance, concurrent Java engine.
- Demonstrate applied knowledge of core Data Structures (Priority Queue) and Operating System concepts (Concurrency, Locks).

## 4. Features
- **User Authentication:** Registration, Login, Logout, Profile management, Secure password hashing.
- **Role-Based Access Control:** Distinct USER and ADMIN roles and dashboards.
- **Auction Management:** Admins can create, edit, and delete auctions with image uploads.
- **Real-Time Bidding:** Users can place bids on active auctions.
- **Analytics Dashboards:** Comprehensive user history and administrative statistics.

## 5. System Architecture
- **Frontend:** HTML5, Vanilla CSS (custom design system), Vanilla JavaScript.
- **Backend (API layer):** Python (Flask) handling HTTP requests, sessions, database interactions, and routing.
- **Backend (Engine layer):** Java HTTP Server handling the memory-intensive, concurrent bid validations and priority queues.
- **Database:** SQLite for persistent storage of users, auctions, and bids.

## 6. Technology Stack
- **Languages:** HTML, CSS, JavaScript, Python, Java, SQL
- **Frameworks:** Flask, Flask-CORS
- **Server:** Python `http.server` (Frontend), Flask Werkzeug (API), `com.sun.net.httpserver` (Java Engine)

## 7. Data Structures
The core data structure used is the **Priority Queue** (Max-Heap), implemented in the Java engine.

## 8. Priority Queue Implementation
In Java, `PriorityQueue<Bid>` is used with a custom comparator that orders bids in descending order based on the bid amount. This transforms the default min-heap into a max-heap.
- **Why?** An auction always needs to know the *highest* current bid instantly. A max-heap provides `O(1)` access to the maximum element (the highest bid).
- **Insertion:** When a new bid is placed, it is inserted in `O(log n)` time.

## 9. Concurrency Control
Since multiple users can bid on the same item simultaneously via HTTP requests, the system is multi-threaded. Without control, two identical highest bids might be accepted simultaneously.

## 10. ReentrantLock
To solve the race condition, Java's `ReentrantLock` is utilized in the `Auction` class.
- When a bid request arrives, the thread must acquire the lock before validating and inserting the bid.
- The validation and insertion block is the **critical section**.
- `try-finally` blocks are strictly used to ensure `lock.unlock()` is always called, preventing deadlocks if an exception occurs.

## 11. Bid Validation
Bid validation occurs authoritatively in the Java Engine:
- The bid amount must be strictly greater than the current highest bid (or starting price).
- The bid must meet the minimum increment threshold (e.g., current highest + increment).
- Bids must be positive and within reasonable numeric bounds.

## 12. Database Design
- `users`: id, username, email, password_hash, role
- `auctions`: id, title, description, starting_price, minimum_increment, start_time, end_time, status, image_path, current_highest_bid
- `bids`: id, auction_id, user_id, bidder_name, amount, created_at
- `email_otps`: Used for password reset tracking (delivery deferred).

## 13. Authentication
- Managed via Flask server-side sessions.
- Passwords are never stored in plaintext (hashed via Werkzeug's `generate_password_hash`).
- `user_id` identity is strictly pulled from the secure server session, ignoring client-side spoofing attempts.

## 14. Admin System
- Dedicated `/api/admin/*` routes protected by `@require_admin` decorator.
- Dashboard provides real-time statistics (Total Users, Active Auctions, Highest Bid).
- Full CRUD access to auctions.

## 15. User Profile
- Displays the user's account details.
- Allows for username and password updates.
- Aggregates auction history (Wins, Losses, Outbid statuses).

## 16. User Analytics
- Provides visual SVG charts of the user's bidding activity over the last 14 days.
- Calculates total bids placed and highest individual bid.

## 17. Admin Analytics
- Aggregates overall system health.
- Calculates active/upcoming/ended ratios.
- Provides a master 14-day bid activity chart across the entire platform.

## 18. Security
- **Authentication:** Session-cookie based with `HttpOnly`.
- **Authorization:** Route-level decorators prevent role escalation.
- **SQL Injection:** Prevented by using parameterized `?` queries in SQLite.
- **Password Exposure:** Hashes are excluded from JSON responses.
- **File Uploads:** Validated and sanitized via `secure_filename`.

## 19. Testing
- Verified concurrent bid behavior via the built-in Java simulation (`/api/admin/simulate`).
- End-to-end testing of user flows, admin protections, and database persistence restarts.

## 20. Limitations
- Email/OTP delivery is currently disabled/deferred (requires active SMTP configuration).
- System relies on cross-port localhost communication in development, which requires specific CORS configurations.

## 21. Future Enhancements
- WebSockets for real-time bid updates on the frontend without polling.
- Full SMTP integration for email verification.
- Migration from SQLite to PostgreSQL for distributed deployments.

## 22. Deployment Considerations
- The current setup is heavily tailored for local development (3 distinct servers).
- Production deployment will require reverse proxying (e.g., Nginx) to unify ports, WSGI application servers (e.g., Gunicorn) for Flask, and secure environment variables for secrets.
