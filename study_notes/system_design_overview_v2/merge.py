import os
import re


def merge_markdown_files():
    """
    Finds all markdown files named "ch_XX_...", sorts them numerically,
    and merges them into a single "combined.md" file.
    """
    output_filename = 'combined.md'
    directory = '.'  # Current directory

    # 1. Get a list of all files in the directory.
    all_files = os.listdir(directory)

    # 2. Filter for markdown files that match the chapter format "ch_XX_...".
    markdown_files = [f for f in all_files if f.startswith('ch_') and f.endswith('.md')]

    # 3. Sort files numerically based on the chapter number (the "XX" in "ch_XX_...").
    #    This ensures "ch_10" comes after "ch_9".
    markdown_files.sort(key=lambda f: int(re.search(r'ch_(\d+)_', f).group(1)))

    # 4. Open the output file in write mode with UTF-8 encoding.
    try:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            for i, filename in enumerate(markdown_files):
                filepath = os.path.join(directory, filename)
                with open(filepath, 'r', encoding='utf-8') as infile:
                    # Read the content and write it to the combined file.
                    outfile.write(infile.read())

                # Add two newlines between files to ensure proper spacing.
                if i < len(markdown_files) - 1:
                    outfile.write('\n\n')

        print(f"Success! Merged {len(markdown_files)} markdown files into {output_filename}")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    merge_markdown_files()