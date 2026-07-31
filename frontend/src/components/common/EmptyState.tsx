interface EmptyStateProps {
  message: string;
}

export function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="text-center text-secondary py-5 border rounded-3 bg-body-tertiary">
      <p className="mb-0">{message}</p>
    </div>
  );
}
