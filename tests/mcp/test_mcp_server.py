"""
Tests for MCP (Model Context Protocol) server.
"""
import pytest
from fastapi.testclient import TestClient


def get_client():
    from backend.app.main import app
    return TestClient(app)


class TestMCPServer:
    """Test MCP protocol endpoints."""
    
    def test_mcp_info_get(self):
        c = get_client()
        r = c.get("/mcp")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "normoscan-mcp"
        assert "tools" in data
    
    def test_mcp_initialize(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["jsonrpc"] == "2.0"
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"
    
    def test_mcp_tools_list(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        })
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
        tools = data["result"]["tools"]
        assert len(tools) > 0
        
        tool_names = [t["name"] for t in tools]
        assert "check_drawing" in tool_names
        assert "ask_gost" in tool_names
        assert "ask_document" in tool_names
        assert "search_gallery" in tool_names
        assert "get_check_status" in tool_names
    
    def test_mcp_ask_gost(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "ask_gost",
                "arguments": {"query": "ГОСТ 2.104", "top_k": 2}
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
    
    def test_mcp_get_metrics(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "get_metrics",
                "arguments": {}
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert "result" in data
    
    def test_mcp_unknown_tool(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {}
            }
        })
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
    
    def test_mcp_unknown_method(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 5,
            "method": "unknown/method"
        })
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
    
    def test_mcp_ping(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 6,
            "method": "ping"
        })
        assert r.status_code == 200
        data = r.json()
        assert data["jsonrpc"] == "2.0"
    
    def test_mcp_parse_error(self):
        c = get_client()
        r = c.post("/mcp", data="not json", headers={"Content-Type": "application/json"})
        assert r.status_code == 200
        data = r.json()
        assert "error" in data
    
    def test_mcp_batch_request(self):
        c = get_client()
        r = c.post("/mcp", json=[
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        ])
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 2
    
    def test_mcp_api_alias(self):
        """Test /api/mcp alias works the same as /mcp."""
        c = get_client()
        r = c.get("/api/mcp")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "normoscan-mcp"


class TestMCPToolSchemas:
    """Test MCP tool input schemas."""
    
    def test_check_drawing_schema(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        })
        tools = r.json()["result"]["tools"]
        check_drawing = next(t for t in tools if t["name"] == "check_drawing")
        
        assert "inputSchema" in check_drawing
        props = check_drawing["inputSchema"]["properties"]
        assert "file_path" in props
        assert "check_id" in props
        assert "priority" in props
    
    def test_ask_gost_schema(self):
        c = get_client()
        r = c.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        })
        tools = r.json()["result"]["tools"]
        ask_gost = next(t for t in tools if t["name"] == "ask_gost")
        
        assert "inputSchema" in ask_gost
        props = ask_gost["inputSchema"]["properties"]
        assert "query" in props
        assert "top_k" in props
        assert "query" in ask_gost["inputSchema"].get("required", [])
