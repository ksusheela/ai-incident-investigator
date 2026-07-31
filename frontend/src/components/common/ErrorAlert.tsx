interface ErrorAlertProps {
  title?: string;
  message: string;
}

export function ErrorAlert({ title = "Something went wrong", message }: ErrorAlertProps) {
  return (
    <div className="alert alert-danger" role="alert">
      <h6 className="alert-heading mb-1">{title}</h6>
      <p className="mb-0 small">{message}</p>
    </div>
  );
}
