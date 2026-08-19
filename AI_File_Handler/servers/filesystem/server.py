from mcp.server.fastmcp import FastMCP

from servers.filesystem.tools import (
    create_file,
    read_file,
    write_file,
    delete_file
)

mcp = FastMCP("Filesystem Server")

@mcp.tool()
def create_file_tool(filename: str) -> str:
    """
    Create an empty file inside the workspace.
    """
    return create_file(filename)


@mcp.tool()
def read_file_tool(filename: str) -> str:
    """
    Read the contents of a file from the workspace.
    """
    return read_file(filename)


@mcp.tool()
def write_file_tool(filename: str, content: str) -> str:
    """
    Write content to a file inside the workspace.
    """
    return write_file(
        filename,
        content
    )


@mcp.tool()
def delete_file_tool(filename: str) -> str:
    """
    Delete a file from the workspace.
    """
    return delete_file(filename)


if __name__ == "__main__":
    mcp.run()