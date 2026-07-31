import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="text-center py-5">
      <h1 className="h4">Page not found</h1>
      <p className="text-secondary">The page you're looking for doesn't exist.</p>
      <Link to="/" className="btn btn-primary">
        Back to dashboard
      </Link>
    </div>
  );
}
