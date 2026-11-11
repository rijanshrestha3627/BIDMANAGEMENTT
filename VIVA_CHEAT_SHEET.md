# Viva Cheat Sheet: University Auction Bid Management System

This document contains short, direct answers to common academic viva questions regarding the technical implementation of this project.

## Data Structures

**Q: Why use a PriorityQueue?**
**A:** In an auction, we constantly need to know the highest bid. A PriorityQueue (configured as a max-heap) allows us to retrieve the maximum value in `O(1)` time, which is incredibly efficient compared to sorting a list every time a bid is placed.

**Q: What is max-heap behavior?**
**A:** A max-heap is a tree-based data structure where the parent node is always greater than or equal to its children. The absolute maximum value is always at the root of the tree.

**Q: Why is insertion O(log n)?**
**A:** When a new bid is added to the PriorityQueue, it is placed at the bottom of the tree and then "bubbles up" to its correct position. The maximum number of swaps is the height of the tree, which is `log n`.

**Q: Why is peek O(1)?**
**A:** The highest bid is always maintained at the very root of the heap. Accessing the root node requires no searching or sorting; it is an instant `O(1)` operation.

## Operating Systems & Concurrency

**Q: What is a ReentrantLock?**
**A:** A ReentrantLock is a mutual exclusion mechanism in Java. It allows a thread to lock a resource. "Reentrant" means if a thread already holds the lock, it can acquire it again without deadlocking itself.

**Q: Why use concurrency in this project?**
**A:** Web servers handle multiple HTTP requests simultaneously. If two users click "Bid" at the exact same millisecond, two separate threads process those bids. We need concurrency controls to prevent race conditions from corrupting the bid state.

**Q: What is a critical section?**
**A:** A critical section is a block of code that accesses shared resources (like our current highest bid variable and the PriorityQueue) and must not be executed by more than one thread at a time.

**Q: Why use lock() and unlock() in a try-finally block?**
**A:** If an error occurs inside the critical section (e.g., a validation exception), the `finally` block guarantees that `lock.unlock()` is called. If we didn't do this, the lock would remain held forever, and the auction would freeze (deadlock).

**Q: What happens when two users bid simultaneously?**
**A:** Both threads attempt to acquire the ReentrantLock. One succeeds and enters the critical section to validate and save its bid. The other thread is paused (blocked). Once the first thread unlocks, the second thread enters, but now sees the *updated* highest bid and is validated against that new value.

## Architecture

**Q: Why use Java for the auction engine?**
**A:** Java has excellent, mature, low-level concurrency controls (`ReentrantLock`, `java.util.concurrent`) and built-in Data Structures (`PriorityQueue`). It is highly suited for the high-frequency, thread-safe memory operations required by a real-time auction.

**Q: Why use Python / Flask?**
**A:** Flask is lightweight and excellent for rapid API development, routing, session management, and database interactions. It acts as the bridge between the frontend user and the Java engine.

**Q: Why use SQLite?**
**A:** SQLite is a serverless, file-based relational database. It is perfect for this project because it requires zero configuration, stores data persistently across restarts, and supports standard SQL queries.

**Q: How does Java communicate with Flask?**
**A:** They communicate over HTTP. The Java engine runs a lightweight internal HTTP server on port 9090. Flask acts as an HTTP client, making internal API requests to Java to place bids or fetch queue status.

## Security

**Q: How is user identity secured?**
**A:** Identity is secured using server-side Flask sessions. The server assigns an encrypted cookie to the user upon login. When a bid is placed, the server reads the `user_id` from the secure session, NOT from the JavaScript request, making it impossible for a user to spoof another user's ID.

**Q: How are passwords stored?**
**A:** Passwords are never stored in plaintext. They are hashed using `werkzeug.security.generate_password_hash` (which uses PBKDF2/scrypt under the hood) before being saved to SQLite.

**Q: How are admin routes protected?**
**A:** We use a custom Python decorator (`@require_admin`). Before executing the route, the decorator checks the session for a `user_id` and verifies the `role == 'ADMIN'`. If not, it returns a 403 Forbidden error immediately.

**Q: How does persistence work after restart?**
**A:** All confirmed bids are written to the SQLite database. If the Java engine is restarted, its memory is wiped. However, when the Flask app starts, it reads all auctions and bids from SQLite and sends them back to Java to reconstruct the PriorityQueue exactly as it was.
