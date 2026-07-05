interface LoadingStepsProps {
  activeStep: number
}

const STEPS = ['规划问题', '检索证据', '生成回答', '完成']

export function LoadingSteps({ activeStep }: LoadingStepsProps) {
  return (
    <div className="loading-steps card" role="status" aria-live="polite" aria-busy="true">
      <div className="loading-steps-header">
        <span className="spinner" aria-hidden="true" />
        <strong>正在处理您的问题…</strong>
      </div>
      <ol className="loading-steps-list">
        {STEPS.map((label, index) => {
          const state = index < activeStep ? 'done' : index === activeStep ? 'active' : 'pending'
          return (
            <li key={label} className={`loading-step loading-step--${state}`}>
              <span className="loading-step-marker" aria-hidden="true" />
              {label}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
