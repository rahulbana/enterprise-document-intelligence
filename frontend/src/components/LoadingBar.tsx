// Name: Rahul Singh Bana
// Email: bana.saa@gmail.com
// LinkedIn: https://www.linkedin.com/in/rahulsinghbana
//
// Indeterminate progress bar shown in place of a bare "Loading…" line while
// a table's data is in flight — duration is unknown (this app talks to a
// remote Postgres, so a page load takes long enough to be worth more than
// plain text), so it sweeps rather than fills to a percentage.

export function LoadingBar({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="d-flex flex-column gap-2">
      <p className="small text-body-secondary mb-0">{label}</p>
      <div className="progress" style={{ height: 6 }} role="progressbar" aria-label={label}>
        <div className="progress-bar loading-sweep-bar" />
      </div>
    </div>
  )
}
