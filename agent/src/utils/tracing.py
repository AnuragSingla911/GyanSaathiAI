import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar

# Context variable for trace ID
trace_context: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)

logger = logging.getLogger(__name__)

class SimpleTracer:
    """Simple tracing implementation for development"""
    
    def __init__(self):
        self.traces: Dict[str, Dict[str, Any]] = {}
    
    def start_trace(self, operation: str, **metadata) -> str:
        """Start a new trace"""
        trace_id = str(uuid.uuid4())
        trace_context.set(trace_id)
        
        self.traces[trace_id] = {
            "trace_id": trace_id,
            "operation": operation,
            "start_time": datetime.utcnow(),
            "metadata": metadata,
            "spans": [],
            "status": "started"
        }
        
        logger.info(f"Started trace {trace_id} for operation: {operation}")
        return trace_id
    
    def add_span(self, name: str, **data):
        """Add a span to the current trace"""
        trace_id = trace_context.get()
        if not trace_id or trace_id not in self.traces:
            return
        
        span = {
            "name": name,
            "timestamp": datetime.utcnow(),
            "data": data
        }
        
        self.traces[trace_id]["spans"].append(span)
        logger.debug(f"Added span '{name}' to trace {trace_id}")
    
    def finish_trace(self, status: str = "completed", **result_data):
        """Finish the current trace"""
        trace_id = trace_context.get()
        if not trace_id or trace_id not in self.traces:
            return
        
        trace = self.traces[trace_id]
        trace["end_time"] = datetime.utcnow()
        trace["duration_ms"] = int((trace["end_time"] - trace["start_time"]).total_seconds() * 1000)
        trace["status"] = status
        trace["result"] = result_data
        
        logger.info(f"Finished trace {trace_id} with status: {status} (duration: {trace['duration_ms']}ms)")
        
        # In production, this would send to observability platform
        self._log_trace_summary(trace)
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get trace by ID"""
        return self.traces.get(trace_id)
    
    def _log_trace_summary(self, trace: Dict[str, Any]):
        """Log trace summary"""
        logger.info(
            f"TRACE_SUMMARY: {trace['operation']} | "
            f"Duration: {trace['duration_ms']}ms | "
            f"Status: {trace['status']} | "
            f"Spans: {len(trace['spans'])}"
        )

# Global tracer instance
_tracer = SimpleTracer()

def get_tracer() -> SimpleTracer:
    """Get the global tracer instance"""
    return _tracer

def setup_tracing():
    """Setup tracing configuration"""
    logger.info("🔍 Simple tracing initialized")

def trace_operation(operation: str):
    """Decorator for tracing operations"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            trace_id = _tracer.start_trace(operation)
            try:
                result = await func(*args, **kwargs)
                _tracer.finish_trace("completed", result={"success": True})
                return result
            except Exception as e:
                _tracer.finish_trace("error", error=str(e))
                raise
        
        def sync_wrapper(*args, **kwargs):
            trace_id = _tracer.start_trace(operation)
            try:
                result = func(*args, **kwargs)
                _tracer.finish_trace("completed", result={"success": True})
                return result
            except Exception as e:
                _tracer.finish_trace("error", error=str(e))
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def add_trace_data(name: str, **data):
    """Add data to the current trace"""
    _tracer.add_span(name, **data)
