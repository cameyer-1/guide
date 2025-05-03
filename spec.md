Python file to print tree given current path
Example Usage: `python dirtree.py C:\Users\YourUser\Documents`

```python
import os
import argparse

# Define connector characters for the tree structure
PREFIX_MIDDLE = "├── "
PREFIX_LAST = "└── "
PREFIX_PARENT_MIDDLE = "│   "
PREFIX_PARENT_LAST = "    "

def print_tree(directory_path, prefix=""):
    """
    Recursively lists the contents of a directory in a tree format.

    Args:
        directory_path (str): The path to the directory to list.
        prefix (str): The prefix string for indentation and connectors,
                      accumulated during recursion.
    """
    try:
        # Get entries and sort them for consistent output
        # Using scandir is often more efficient than listdir as it fetches file type info
        entries = sorted([entry for entry in os.scandir(directory_path)], key=lambda e: e.name)
    except PermissionError:
        print(f"{prefix}{PREFIX_LAST}[Permission Denied]")
        return
    except FileNotFoundError:
        print(f"{prefix}{PREFIX_LAST}[Error: Not Found - Potential broken link?]")
        return

    entry_count = len(entries)
    for i, entry in enumerate(entries):
        is_last = (i == entry_count - 1)

        # Determine the connector for the current item
        connector = PREFIX_LAST if is_last else PREFIX_MIDDLE

        # Print the current entry (file or directory)
        print(f"{prefix}{connector}{entry.name}")

        # If it's a directory, recurse into it
        if entry.is_dir():
            # Determine the prefix for the items inside this directory
            # If the current directory is the last item, its children don't need the vertical line
            # Otherwise, they do need the vertical line continuation
            extension = PREFIX_PARENT_LAST if is_last else PREFIX_PARENT_MIDDLE
            print_tree(entry.path, prefix + extension)

def main():
    """
    Parses command-line arguments and initiates the tree printing.
    """
    parser = argparse.ArgumentParser(
        description="Recursively prints the file tree structure starting from a given directory."
    )
    parser.add_argument(
        "root_dir",
        metavar="DIRECTORY_PATH",
        nargs='?',  # Make the argument optional
        default='.', # Default to current directory if no path is provided
        help="The root directory to start the tree from (defaults to the current directory)."
    )

    args = parser.parse_args()
    root_directory = args.root_dir

    # --- Input Validation ---
    # Get absolute path for clarity and consistency
    try:
        abs_root_path = os.path.abspath(root_directory)
    except Exception as e:
        print(f"Error processing path '{root_directory}': {e}")
        return

    if not os.path.exists(abs_root_path):
        print(f"Error: Path does not exist: '{abs_root_path}'")
        return

    if not os.path.isdir(abs_root_path):
        print(f"Error: Path is not a directory: '{abs_root_path}'")
        return

    # --- Start Printing ---
    # Print the root directory name itself first
    print(f"{os.path.basename(abs_root_path)}/") # Indicate it's the root directory

    # Start the recursive printing process from the validated root directory
    print_tree(abs_root_path)

if __name__ == "__main__":
    main()
```
