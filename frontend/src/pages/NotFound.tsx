import { Link } from 'react-router-dom'
import { PageHeader } from '../components/PageShell'

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="页面未找到" subtitle="您访问的路径不存在。" />
      <div className="card">
        <p>请检查 URL，或返回工作区首页继续研究。</p>
        <Link to="/" className="btn">
          返回科研问答
        </Link>
      </div>
    </>
  )
}
