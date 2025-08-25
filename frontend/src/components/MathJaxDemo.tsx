import React from 'react';
import { Box, Card, CardContent, Typography, Divider } from '@mui/material';
import MathJaxRenderer from './MathJaxRenderer';

const MathJaxDemo: React.FC = () => {
  const mathExamples = [
    {
      title: 'Inline Math Examples',
      examples: [
        'The quadratic formula is $x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$',
        'Euler\'s identity: $e^{i\\pi} + 1 = 0$',
        'The derivative of $f(x) = x^2$ is $f\'(x) = 2x$',
        'Pythagorean theorem: $a^2 + b^2 = c^2$'
      ]
    },
    {
      title: 'Display Math Examples',
      examples: [
        '$$\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}$$',
        '$$\\sum_{n=1}^{\\infty} \\frac{1}{n^2} = \\frac{\\pi^2}{6}$$',
        '$$\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix} \\begin{pmatrix} x \\\\ y \\end{pmatrix} = \\begin{pmatrix} ax + by \\\\ cx + dy \\end{pmatrix}$$',
        '$$\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1$$'
      ]
    },
    {
      title: 'Complex Mathematical Expressions',
      examples: [
        '$$\\frac{d}{dx}\\left[\\int_{0}^{x} f(t) dt\\right] = f(x)$$',
        '$$\\oint_C \\vec{F} \\cdot d\\vec{r} = \\iint_S (\\nabla \\times \\vec{F}) \\cdot d\\vec{S}$$',
        '$$\\begin{align*} (a + b)^2 &= a^2 + 2ab + b^2 \\\\ &= a^2 + b^2 + 2ab \\end{align*}$$'
      ]
    }
  ];

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 700, mb: 3 }}>
        MathJax Rendering Examples
      </Typography>
      
      {mathExamples.map((section, sectionIdx) => (
        <Card key={sectionIdx} sx={{ mb: 3, borderRadius: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: 'primary.main' }}>
              {section.title}
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            {section.examples.map((example, exampleIdx) => (
              <Box key={exampleIdx} sx={{ mb: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontFamily: 'monospace' }}>
                  {example}
                </Typography>
                <Box sx={{ mt: 1 }}>
                  <MathJaxRenderer 
                    content={example} 
                    displayMode={section.title.includes('Display') ? 'block' : 'inline'}
                    showLoading={true}
                  />
                </Box>
              </Box>
            ))}
          </CardContent>
        </Card>
      ))}
      
      <Card sx={{ borderRadius: 2, bgcolor: 'info.light' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
            Usage Instructions
          </Typography>
          <Typography variant="body2" paragraph>
            • Use <code>$...$</code> for inline math expressions<br/>
            • Use <code>$$...$$</code> for display math expressions<br/>
            • LaTeX syntax is fully supported<br/>
            • Math expressions are automatically rendered when content changes
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default MathJaxDemo;
