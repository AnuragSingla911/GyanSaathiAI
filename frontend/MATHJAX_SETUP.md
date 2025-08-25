# MathJax Integration Guide

This document explains how MathJax is integrated into the AI Tutor frontend to render mathematical content.

## Overview

MathJax is a JavaScript library that renders mathematical notation in web browsers using LaTeX, MathML, or AsciiMath notation. It's integrated into our frontend to display mathematical content in questions, answers, and explanations.

## Setup

### 1. CDN Integration

MathJax is loaded via CDN in `index.html`:

```html
<!-- MathJax Configuration -->
<script>
  window.MathJax = {
    tex: {
      inlineMath: [['$', '$'], ['\\(', '\\)']],
      displayMath: [['$$', '$$'], ['\\[', '\\]']],
      processEscapes: true,
      processEnvironments: true
    },
    options: {
      skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
    }
  };
</script>

<!-- MathJax Library -->
<script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
```

### 2. Configuration Options

- **inlineMath**: Delimiters for inline math expressions (`$...$` and `\(...\)`)
- **displayMath**: Delimiters for display math expressions (`$$...$$` and `\[...\]`)
- **processEscapes**: Enables backslash escaping
- **processEnvironments**: Enables LaTeX environments

## Components

### MathJaxRenderer

The main component for rendering mathematical content:

```tsx
import MathJaxRenderer from '../components/MathJaxRenderer';

<MathJaxRenderer 
  content="The quadratic formula is $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$"
  displayMode="inline"
  showLoading={true}
  fallbackText="Math content could not be rendered"
/>
```

#### Props

- `content`: String containing math expressions
- `displayMode`: 'inline' or 'block' rendering
- `showLoading`: Show loading spinner while rendering
- `fallbackText`: Text to display if rendering fails

### MathJaxDemo

A demonstration component showcasing various math examples:

```tsx
import MathJaxDemo from '../components/MathJaxDemo';

<MathJaxDemo />
```

## Usage Examples

### Inline Math

```tsx
// Simple inline expression
<MathJaxRenderer content="The value of π is $\\pi \\approx 3.14159$" />

// With variables
<MathJaxRenderer content="For $x = 5$, we have $x^2 = 25$" />
```

### Display Math

```tsx
// Block-level equation
<MathJaxRenderer 
  content="$$\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}$$"
  displayMode="block"
/>
```

### Complex Expressions

```tsx
// Matrix
<MathJaxRenderer 
  content="$$\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}$$"
  displayMode="block"
/>

// Aligned equations
<MathJaxRenderer 
  content="$$\\begin{align*} (a + b)^2 &= a^2 + 2ab + b^2 \\\\ &= a^2 + b^2 + 2ab \\end{align*}$$"
  displayMode="block"
/>
```

## LaTeX Syntax Support

### Basic Math

- **Fractions**: `\frac{numerator}{denominator}`
- **Superscripts**: `x^2`, `e^{i\pi}`
- **Subscripts**: `x_i`, `a_{n+1}`
- **Square roots**: `\sqrt{x}`, `\sqrt[n]{x}`

### Greek Letters

- `\alpha`, `\beta`, `\gamma`, `\delta`
- `\pi`, `\theta`, `\phi`, `\omega`
- `\Pi`, `\Theta`, `\Phi`, `\Omega`

### Operators

- **Integrals**: `\int`, `\oint`, `\iint`
- **Sums**: `\sum_{i=1}^{n}`, `\prod_{i=1}^{n}`
- **Limits**: `\lim_{x \to 0}`, `\limsup`, `\liminf`

### Environments

- **Matrices**: `\begin{pmatrix} ... \end{pmatrix}`
- **Cases**: `\begin{cases} ... \end{cases}`
- **Align**: `\begin{align*} ... \end{align*}`

## Integration in Quiz System

MathJax is automatically applied to:

1. **Question text** - Rendered as block display
2. **Answer options** - Rendered as inline display
3. **Results display** - Both question and answer text
4. **Explanations** - Mathematical content in explanations

## Error Handling

The system includes robust error handling:

- Loading states with spinners
- Fallback text for failed renders
- Retry mechanisms
- Console warnings for debugging

## Performance Considerations

- MathJax is loaded asynchronously
- Rendering is debounced to prevent excessive re-renders
- Content is processed efficiently with regex
- Loading states provide visual feedback

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES6 polyfill included for older browsers
- Responsive design for mobile devices

## Troubleshooting

### Common Issues

1. **Math not rendering**: Check if MathJax is loaded
2. **Syntax errors**: Verify LaTeX syntax
3. **Performance issues**: Check for excessive re-renders

### Debug Mode

Enable console logging by checking the browser console for MathJax-related messages.

## Future Enhancements

- Support for MathML input
- Custom math symbol definitions
- MathJax configuration customization
- Performance optimizations
- Accessibility improvements

## Resources

- [MathJax Documentation](https://docs.mathjax.org/)
- [LaTeX Math Symbols](https://oeis.org/wiki/List_of_LaTeX_mathematical_symbols)
- [MathJax Examples](https://mathjax.github.io/MathJax-demos-web/)
