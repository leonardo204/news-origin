import { Component, type ReactNode } from 'react'
import { Button } from './Button'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex min-h-[40vh] flex-col items-center justify-center gap-4 p-8">
          <div className="text-center">
            <h2 className="mb-2 text-lg font-semibold text-destructive">
              오류가 발생했습니다
            </h2>
            <p className="text-sm text-muted-foreground">
              {this.state.error?.message || '예기치 않은 오류가 발생했습니다.'}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.reload()
            }}
          >
            페이지 새로고침
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
