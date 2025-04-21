from collections import deque
import asyncio

# In-memory queue for customers with unresponded messages (FIFO)
customer_queue = deque()
# Active conversation state (phone_number of the current customer being handled)
active_conversation = None
# Lock for thread-safe queue operations
queue_lock = asyncio.Lock()
