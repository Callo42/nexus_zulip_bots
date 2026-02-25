"""Tests for LaTeX to Zulip KaTeX conversion."""

import unittest

from src.formatters import convert_latex_to_zulip_katex


class TestConvertLatexToZulipKatex(unittest.TestCase):
    """Tests for the convert_latex_to_zulip_katex function."""

    def test_empty_string(self):
        """Return empty string unchanged."""
        self.assertEqual(convert_latex_to_zulip_katex(""), "")

    def test_no_math(self):
        """Return text without math delimiters unchanged."""
        text = "Hello, this is a normal message without any math."
        self.assertEqual(convert_latex_to_zulip_katex(text), text)

    def test_none_input(self):
        """Return None unchanged."""
        self.assertIsNone(convert_latex_to_zulip_katex(None))

    def test_inline_math_single_dollar(self):
        """Convert $...$ to $$...$$ for inline math."""
        text = "The value is $x + y$ in this equation."
        expected = "The value is $$x + y$$ in this equation."
        self.assertEqual(convert_latex_to_zulip_katex(text), expected)

    def test_multiple_inline_math(self):
        """Convert multiple inline math expressions."""
        text = "We have $x = 1$ and $y = 2$."
        expected = "We have $$x = 1$$ and $$y = 2$$."
        self.assertEqual(convert_latex_to_zulip_katex(text), expected)

    def test_display_math_double_dollar(self):
        """Convert $$...$$ to ```math fence for display math."""
        text = "Here is a formula:\n$$\na_{ij} = \\frac{x}{y}\n$$\nEnd."
        result = convert_latex_to_zulip_katex(text)
        self.assertIn("```math", result)
        self.assertIn("a_{ij} = \\frac{x}{y}", result)
        self.assertNotIn("$$", result)

    def test_display_math_single_line(self):
        """Convert single-line $$...$$ to ```math fence."""
        text = "Formula: $$E = mc^2$$ is famous."
        result = convert_latex_to_zulip_katex(text)
        self.assertIn("```math", result)
        self.assertIn("E = mc^2", result)

    def test_mixed_inline_and_display(self):
        """Convert both inline and display math in same text."""
        text = "Inline $x$ and display:\n$$\ny = mx + b\n$$\nDone."
        result = convert_latex_to_zulip_katex(text)
        # Inline should become $$x$$
        self.assertIn("$$x$$", result)
        # Display should become ```math
        self.assertIn("```math", result)
        self.assertIn("y = mx + b", result)

    def test_code_block_preserved(self):
        """Do not convert math inside fenced code blocks."""
        text = "Look at this:\n```python\nx = $y + 1$\n```\nBut $a$ here."
        result = convert_latex_to_zulip_katex(text)
        # Code block should be unchanged
        self.assertIn("```python\nx = $y + 1$\n```", result)
        # Outside code block should be converted
        self.assertIn("$$a$$", result)

    def test_inline_code_preserved(self):
        """Do not convert math inside inline code."""
        text = "Use `$variable` or $x + 1$ in math."
        result = convert_latex_to_zulip_katex(text)
        # Inline code should be preserved
        self.assertIn("`$variable`", result)
        # Math outside inline code should be converted
        self.assertIn("$$x + 1$$", result)

    def test_escaped_dollar_not_converted(self):
        r"""Do not convert escaped dollar signs \$."""
        text = "The price is \\$5 and the value is $x$."
        result = convert_latex_to_zulip_katex(text)
        self.assertIn("\\$5", result)
        self.assertIn("$$x$$", result)

    def test_complex_latex_example(self):
        """Test with a realistic LLM response containing LaTeX."""
        text = (
            "For $0 < x_1 < x_2$, define the matrix $A = (a_{ij})$ by\n"
            "$$\n"
            "a_{ij} = \\frac{\\min(x_i, x_j)}{x_i + x_j}.\n"
            "$$\n"
            "Prove that $\\det A > 0$."
        )
        result = convert_latex_to_zulip_katex(text)
        # Inline math converted
        self.assertIn("$$0 < x_1 < x_2$$", result)
        self.assertIn("$$A = (a_{ij})$$", result)
        self.assertIn("$$\\det A > 0$$", result)
        # Display math converted to fence
        self.assertIn("```math", result)
        self.assertIn("a_{ij} = \\frac{\\min(x_i, x_j)}{x_i + x_j}.", result)

    def test_matrix_display_math(self):
        """Test conversion of display math with matrix environments."""
        text = (
            "$$\n" "A = \\begin{pmatrix} 1/2 & x/(x+y) \\\\\\ x/(x+y) & 1/2 \\end{pmatrix}\n" "$$"
        )
        result = convert_latex_to_zulip_katex(text)
        self.assertIn("```math", result)
        self.assertIn("\\begin{pmatrix}", result)

    def test_already_zulip_format_math_fence(self):
        """Do not double-convert already-formatted math fences."""
        text = "Look:\n```math\nx = 1\n```\nDone."
        result = convert_latex_to_zulip_katex(text)
        # Should remain unchanged since it's inside a code block
        self.assertEqual(result, text)

    def test_no_dollar_sign_fast_path(self):
        """Text without any $ should return immediately unchanged."""
        text = "Just a regular message with no dollar signs."
        self.assertEqual(convert_latex_to_zulip_katex(text), text)

    def test_multiple_display_math_blocks(self):
        """Convert multiple display math blocks."""
        text = "First equation:\n$$\nx^2\n$$\n" "Second equation:\n$$\ny^2\n$$"
        result = convert_latex_to_zulip_katex(text)
        self.assertEqual(result.count("```math"), 2)

    def test_inline_math_with_subscript_superscript(self):
        """Convert inline math with common LaTeX patterns."""
        text = "Consider $x_i^2 + y_j^3$ in context."
        expected = "Consider $$x_i^2 + y_j^3$$ in context."
        self.assertEqual(convert_latex_to_zulip_katex(text), expected)

    def test_integral_display_math(self):
        """Test integral representation in display math."""
        text = "$$\na_{ij} = \\int_0^\\infty \\min(x_i, x_j) e^{-t(x_i + x_j)} \\, dt\n$$"
        result = convert_latex_to_zulip_katex(text)
        self.assertIn("```math", result)
        self.assertIn("\\int_0^\\infty", result)


if __name__ == "__main__":
    unittest.main()
