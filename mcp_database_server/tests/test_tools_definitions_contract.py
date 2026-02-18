from __future__ import annotations

from jsonschema import Draft202012Validator

from mcp_database_server.tools_definitions import get_tool_definitions


def test_tool_definitions_have_expected_stable_names() -> None:
    tools = get_tool_definitions()
    names = [t["name"] for t in tools]
    assert names == ["db_health_check", "db_list_schemas", "db_list_tables", "db_query"]


def test_tool_definitions_shape_and_required_fields() -> None:
    tools = get_tool_definitions()
    assert isinstance(tools, list)
    assert tools, "Expected at least one tool definition"

    for tool in tools:
        assert set(tool.keys()) >= {"name", "description", "inputSchema"}
        assert isinstance(tool["name"], str) and tool["name"]
        assert isinstance(tool["description"], str) and tool["description"]
        assert isinstance(tool["inputSchema"], dict)

        schema = tool["inputSchema"]
        # Strict-schema contract
        assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert schema.get("type") == "object"
        assert schema.get("additionalProperties") is False
        assert "properties" in schema and isinstance(schema["properties"], dict)
        assert "required" in schema and isinstance(schema["required"], list)

        # Should compile under draft 2020-12
        Draft202012Validator.check_schema(schema)


def test_tool_definitions_specific_schema_contracts() -> None:
    tools = {t["name"]: t for t in get_tool_definitions()}

    # db_health_check: no inputs at all
    health_schema = tools["db_health_check"]["inputSchema"]
    assert health_schema["properties"] == {}
    assert health_schema["required"] == []

    # db_list_schemas: optional limit int 1..1000
    schemas_schema = tools["db_list_schemas"]["inputSchema"]
    assert "limit" in schemas_schema["properties"]
    limit = schemas_schema["properties"]["limit"]
    assert limit["type"] == "integer"
    assert limit["minimum"] == 1
    assert limit["maximum"] == 1000
    assert schemas_schema["required"] == []

    # db_list_tables: required schema string, optional limit
    tables_schema = tools["db_list_tables"]["inputSchema"]
    assert "schema" in tables_schema["properties"]
    assert tables_schema["properties"]["schema"]["type"] == "string"
    assert tables_schema["properties"]["schema"]["minLength"] == 1
    assert tables_schema["required"] == ["schema"]

    # db_query: required sql string, optional max_rows
    query_schema = tools["db_query"]["inputSchema"]
    assert query_schema["properties"]["sql"]["type"] == "string"
    assert query_schema["properties"]["sql"]["minLength"] == 1
    assert query_schema["required"] == ["sql"]

    max_rows = query_schema["properties"]["max_rows"]
    assert max_rows["type"] == "integer"
    assert max_rows["minimum"] == 1
    assert max_rows["maximum"] == 1000
