"""Email template rendering with variable substitution."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Renders email templates with variable substitution.

    Supports simple variable substitution using {variable_name} syntax.
    Falls back to generic text if variables are missing (e.g., "Hey" instead of "Hey {name}").
    """

    # Pattern to match {variable_name} in templates
    VARIABLE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

    def render(
        self,
        template: str,
        variables: dict[str, str | None],
        fallback_strategy: str = "remove",
    ) -> str:
        """Render template by substituting variables.

        Args:
            template: Template string with {variable_name} placeholders
            variables: Dictionary of variable name -> value mappings
            fallback_strategy: How to handle missing variables:
                - "remove": Remove the placeholder entirely (default)
                - "keep": Keep the placeholder as-is
                - "empty": Replace with empty string

        Returns:
            Rendered template string

        Examples:
            >>> renderer = TemplateRenderer()
            >>> renderer.render("Hey {name}!", {"name": "Alice"})
            "Hey Alice!"
            >>> renderer.render("Hey {name}!", {})
            "Hey !"
            >>> renderer.render("Hey {name}!", {}, fallback_strategy="remove")
            "Hey !"
        """
        rendered = template

        # Find all variables in template
        matches = self.VARIABLE_PATTERN.findall(template)

        for var_name in matches:
            placeholder = f"{{{var_name}}}"
            value = variables.get(var_name)

            if value is not None and value != "":
                # Replace with actual value
                rendered = rendered.replace(placeholder, value)
            else:
                # Handle missing/empty variable based on strategy
                if fallback_strategy == "remove":
                    rendered = rendered.replace(placeholder, "")
                elif fallback_strategy == "keep":
                    pass  # Keep placeholder as-is
                elif fallback_strategy == "empty":
                    rendered = rendered.replace(placeholder, "")
                else:
                    logger.warning(
                        f"Unknown fallback_strategy: {fallback_strategy}, using 'remove'"
                    )
                    rendered = rendered.replace(placeholder, "")

        # Clean up any double spaces created by variable removal
        rendered = re.sub(r" +", " ", rendered)

        # Clean up space before punctuation
        rendered = re.sub(r" ([.,!?])", r"\1", rendered)

        return rendered.strip()

    def render_with_fallbacks(
        self,
        template: str,
        variables: dict[str, str | None],
        fallbacks: dict[str, str],
    ) -> str:
        """Render template with fallback values for missing variables.

        Args:
            template: Template string
            variables: Primary variable values
            fallbacks: Fallback values if primary values are missing

        Returns:
            Rendered template string

        Example:
            >>> renderer = TemplateRenderer()
            >>> renderer.render_with_fallbacks(
            ...     "Hey {name}!",
            ...     {"name": None},
            ...     {"name": "there"}
            ... )
            "Hey there!"
        """
        # Merge variables with fallbacks (variables take precedence)
        merged = {**fallbacks}
        for key, value in variables.items():
            if value is not None and value != "":
                merged[key] = value

        return self.render(template, merged, fallback_strategy="remove")

    def extract_variables(self, template: str) -> list[str]:
        """Extract list of variable names from template.

        Args:
            template: Template string

        Returns:
            List of variable names found in template

        Example:
            >>> renderer = TemplateRenderer()
            >>> renderer.extract_variables("Hey {name}, your {item} is ready!")
            ["name", "item"]
        """
        return self.VARIABLE_PATTERN.findall(template)

    def validate_template(self, template: str, required_vars: list[str]) -> tuple[bool, list[str]]:
        """Validate that template contains all required variables.

        Args:
            template: Template string
            required_vars: List of required variable names

        Returns:
            Tuple of (is_valid, missing_variables)

        Example:
            >>> renderer = TemplateRenderer()
            >>> renderer.validate_template("Hey {name}!", ["name", "email"])
            (False, ["email"])
        """
        found_vars = set(self.extract_variables(template))
        required_set = set(required_vars)
        missing = list(required_set - found_vars)

        is_valid = len(missing) == 0
        return is_valid, missing


# Global instance
template_renderer = TemplateRenderer()
