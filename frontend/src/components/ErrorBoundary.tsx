import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary — catches render errors and shows a fallback UI
 * instead of crashing the whole app with a white screen.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-retro-bg text-gray-300 p-8">
          <div className="max-w-md text-center space-y-4">
            <div className="text-4xl text-retro-red font-mono">!</div>
            <h1 className="text-lg font-bold text-retro-red uppercase tracking-wider">
              Unexpected Error
            </h1>
            <p className="text-sm text-gray-500 font-mono">
              {this.state.error?.message ?? 'An unknown error occurred.'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 border border-retro-border bg-retro-bg text-sm text-retro-cyan hover:bg-retro-hover transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
