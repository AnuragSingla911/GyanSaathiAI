import React, { useEffect, useRef, useState } from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';
import './MathJaxRenderer.css';

interface MathJaxRendererProps {
  content: string;
  displayMode?: 'inline' | 'block';
  className?: string;
  showLoading?: boolean;
  fallbackText?: string;
}

declare global {
  interface Window {
    MathJax: {
      typesetPromise: (elements?: HTMLElement[]) => Promise<void>;
      typeset: (elements?: HTMLElement[]) => void;
      startup?: {
        promise: Promise<void>;
      };
    };
  }
}

const MathJaxRenderer: React.FC<MathJaxRendererProps> = ({ 
  content, 
  displayMode = 'inline',
  className = '',
  showLoading = true,
  fallbackText
}) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  const renderMath = async () => {
    if (!contentRef.current) return;

    try {
      setIsLoading(true);
      setHasError(false);

      // Wait for MathJax to be fully loaded
      if (window.MathJax?.startup?.promise) {
        await window.MathJax.startup.promise;
      }

      if (window.MathJax?.typesetPromise) {
        await window.MathJax.typesetPromise([contentRef.current]);
      } else if (window.MathJax?.typeset) {
        window.MathJax.typeset([contentRef.current]);
      } else {
        throw new Error('MathJax not available');
      }

      setIsLoading(false);
    } catch (error) {
      console.warn('MathJax rendering error:', error);
      setHasError(true);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(renderMath, 100);
    return () => clearTimeout(timer);
  }, [content, retryCount]);

  // Function to process content and wrap math expressions
  const processContent = (text: string): string => {
    if (!text) return '';
    
    let processed = text;
    
    // Handle inline math with $...$ (but not $$...$$)
    processed = processed.replace(/(?<!\$)\$([^$]+?)\$(?!\$)/g, (match, math) => {
      return `\\(${math}\\)`;
    });
    
    // Handle display math with $$...$$
    processed = processed.replace(/\$\$([^$]+?)\$\$/g, (match, math) => {
      return `\\[${math}\\]`;
    });
    
    return processed;
  };

  const processedContent = processContent(content);
  const displayClass = displayMode === 'block' ? 'math-display' : 'math-inline';

  const handleRetry = () => {
    setRetryCount(prev => prev + 1);
  };

  if (hasError && fallbackText) {
    return (
      <Box className={className}>
        <Typography 
          variant="body2" 
          color="text.secondary"
          sx={{ fontStyle: 'italic' }}
        >
          {fallbackText}
        </Typography>
        <Typography 
          variant="caption" 
          color="text.secondary"
          sx={{ cursor: 'pointer', textDecoration: 'underline' }}
          onClick={handleRetry}
        >
          Click to retry rendering
        </Typography>
      </Box>
    );
  }

  return (
    <Box 
      className={`${displayClass} ${className}`}
      sx={{
        display: displayMode === 'block' ? 'block' : 'inline',
        width: displayMode === 'block' ? '100%' : 'auto',
        position: 'relative',
        minHeight: isLoading && showLoading ? '20px' : 'auto'
      }}
    >
      {isLoading && showLoading && (
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 1
          }}
        >
          <CircularProgress size={16} />
        </Box>
      )}
      
      <div 
        ref={contentRef}
        dangerouslySetInnerHTML={{ __html: processedContent }}
        style={{
          opacity: isLoading ? 0.3 : 1,
          transition: 'opacity 0.2s ease-in-out'
        }}
      />
    </Box>
  );
};

export default MathJaxRenderer;
