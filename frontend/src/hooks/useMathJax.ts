import { useState, useEffect, useCallback } from 'react';

interface MathJaxState {
  isLoaded: boolean;
  isLoading: boolean;
  hasError: boolean;
}

interface MathJaxHook {
  state: MathJaxState;
  renderMath: (elements?: HTMLElement[]) => Promise<void>;
  isMathJaxAvailable: () => boolean;
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

export const useMathJax = (): MathJaxHook => {
  const [state, setState] = useState<MathJaxState>({
    isLoaded: false,
    isLoading: true,
    hasError: false
  });

  const isMathJaxAvailable = useCallback((): boolean => {
    return !!(window.MathJax && (window.MathJax.typesetPromise || window.MathJax.typeset));
  }, []);

  const renderMath = useCallback(async (elements?: HTMLElement[]): Promise<void> => {
    if (!isMathJaxAvailable()) {
      throw new Error('MathJax is not available');
    }

    try {
      setState(prev => ({ ...prev, isLoading: true, hasError: false }));

      // Wait for MathJax to be fully loaded
      if (window.MathJax?.startup?.promise) {
        await window.MathJax.startup.promise;
      }

      if (window.MathJax.typesetPromise) {
        await window.MathJax.typesetPromise(elements);
      } else if (window.MathJax.typeset) {
        window.MathJax.typeset(elements);
      }

      setState(prev => ({ ...prev, isLoading: false, isLoaded: true }));
    } catch (error) {
      console.error('MathJax rendering error:', error);
      setState(prev => ({ ...prev, isLoading: false, hasError: true }));
      throw error;
    }
  }, [isMathJaxAvailable]);

  useEffect(() => {
    const checkMathJax = () => {
      if (isMathJaxAvailable()) {
        setState(prev => ({ ...prev, isLoaded: true, isLoading: false }));
      } else {
        // Check again after a short delay
        setTimeout(checkMathJax, 100);
      }
    };

    checkMathJax();
  }, [isMathJaxAvailable]);

  return {
    state,
    renderMath,
    isMathJaxAvailable
  };
};
