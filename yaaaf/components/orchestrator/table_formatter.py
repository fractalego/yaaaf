"""
Table formatting utilities for orchestrator response processing.
"""
import logging

_logger = logging.getLogger(__name__)


class TableFormatter:
    """Formats dataframes for markdown display."""
    
    @staticmethod
    def sanitize_dataframe_for_markdown(df) -> str:
        """Sanitize dataframe data to prevent markdown table breakage."""
        # Create a copy to avoid modifying the original
        df_clean = df.copy()

        # Apply sanitization to all string columns
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":  # String columns
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .apply(
                        lambda x: (
                            x.replace("|", "\\|")  # Escape pipe characters
                            .replace("\n", " ")  # Replace newlines with spaces
                            .replace("\r", " ")  # Replace carriage returns
                            .replace("\t", " ")  # Replace tabs with spaces
                            .strip()  # Remove leading/trailing whitespace
                        )
                    )
                )

        return df_clean.to_markdown(index=False)

    @staticmethod
    def sanitize_and_truncate_dataframe_for_markdown(df, max_rows: int = 5) -> str:
        """Sanitize dataframe and truncate to first max_rows, showing ellipsis if truncated."""
        # Create a copy to avoid modifying the original
        df_clean = df.copy()

        # Apply basic sanitization to all string columns - keep it simple to avoid encoding issues
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":  # String columns
                df_clean[col] = (
                    df_clean[col]
                    .astype(str)
                    .apply(
                        lambda x: (
                            # Only do basic cleaning - let frontend handle the rest
                            x.replace("\n", " ")  # Replace newlines with spaces
                            .replace("\r", " ")  # Replace carriage returns
                            .replace("\t", " ")  # Replace tabs with spaces
                            .strip()  # Remove leading/trailing whitespace
                        )
                    )
                )

        # Truncate all cells to 200 characters max
        for col in df_clean.columns:
            df_clean[col] = (
                df_clean[col]
                .astype(str)
                .apply(lambda x: x[:200] + "..." if len(x) > 200 else x)
            )

        # Check if we need to truncate
        is_truncated = len(df_clean) > max_rows
        df_display = df_clean.head(max_rows)

        # Convert to markdown - keep it simple
        markdown_table = df_display.to_markdown(index=False)

        # Add ellipsis indicator if truncated
        if is_truncated:
            total_rows = len(df_clean)
            markdown_table += f"\n\n*... ({total_rows - max_rows} more rows)*"

        return markdown_table