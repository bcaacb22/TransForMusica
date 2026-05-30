import { Component } from 'react';

const styles = {
  container: {
    padding: '24px',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    background: 'rgba(255, 59, 59, 0.04)',
    fontFamily: 'JetBrains Mono, monospace',
  },
  heading: {
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '10px',
    letterSpacing: '0.15em',
    color: 'rgba(255, 255, 255, 0.45)',
    marginBottom: '12px',
  },
  message: {
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '12px',
    color: '#ffffff',
    marginBottom: '8px',
  },
  errorDetail: {
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '11px',
    color: '#ff3b3b',
    marginBottom: '16px',
    opacity: 0.85,
  },
  retryButton: {
    background: 'transparent',
    color: '#00ff88',
    border: '1px solid rgba(0, 255, 136, 0.45)',
    padding: '8px 16px',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '10px',
    letterSpacing: '0.1em',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
};

export class GatewayErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary] Gateway error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" style={styles.container}>
          <div style={styles.heading}>// GATEWAY ERROR</div>
          <p style={styles.message}>Something went wrong in this gateway.</p>
          <p style={styles.errorDetail}>{this.state.error?.message}</p>
          <button onClick={this.handleRetry} style={styles.retryButton}>
            RETRY
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
