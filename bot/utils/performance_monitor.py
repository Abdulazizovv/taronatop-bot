"""
Performance monitoring utility for tracking bot metrics
"""
import time
import logging
import asyncio
from typing import Dict, Any, Optional
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict


class PerformanceMonitor:
    """Performance monitoring class for tracking execution times and statistics"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.counters = defaultdict(int)
        self.start_time = datetime.now()
    
    def time_function(self, func_name: str = None):
        """Decorator to time function execution"""
        def decorator(func):
            name = func_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        self.counters[f"{name}.success"] += 1
                        return result
                    except Exception as e:
                        self.counters[f"{name}.error"] += 1
                        logging.error(f"Error in {name}: {e}")
                        raise
                    finally:
                        execution_time = time.time() - start_time
                        self.metrics[name].append(execution_time)
                        if execution_time > 1.0:  # Log slow operations
                            logging.warning(f"Slow operation detected: {name} took {execution_time:.2f}s")
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    start_time = time.time()
                    try:
                        result = func(*args, **kwargs)
                        self.counters[f"{name}.success"] += 1
                        return result
                    except Exception as e:
                        self.counters[f"{name}.error"] += 1
                        logging.error(f"Error in {name}: {e}")
                        raise
                    finally:
                        execution_time = time.time() - start_time
                        self.metrics[name].append(execution_time)
                        if execution_time > 1.0:
                            logging.warning(f"Slow operation detected: {name} took {execution_time:.2f}s")
                return sync_wrapper
        return decorator
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "function_stats": {},
            "counters": dict(self.counters)
        }
        
        for func_name, times in self.metrics.items():
            if times:
                stats["function_stats"][func_name] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "total_time": sum(times)
                }
        
        return stats
    
    def log_stats(self):
        """Log current statistics"""
        stats = self.get_stats()
        logging.info(f"Performance Stats: {stats}")
    
    def reset_stats(self):
        """Reset all statistics"""
        self.metrics.clear()
        self.counters.clear()
        self.start_time = datetime.now()


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


async def log_stats_periodically(interval: int = 3600):
    """Log statistics periodically"""
    while True:
        await asyncio.sleep(interval)
        performance_monitor.log_stats()
