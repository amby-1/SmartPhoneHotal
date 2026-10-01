interface Bin {
  center: number;
  count: number;
}

interface Props {
  title: string;
  bins: Bin[];
  sampleCount: number;
}

export default function FrequencyChart({ title, bins, sampleCount }: Props) {
  const maxCount = Math.max(1, ...bins.map((b) => b.count));

  return (
    <div className="chart-card">
      <div className="chart-head">
        <h2>{title}</h2>
        <span className="muted">{sampleCount} 人分</span>
      </div>
      {bins.length === 0 ? (
        <p className="muted chart-empty">まだ十分なタップがありません</p>
      ) : (
        <div className="chart-bars" role="img" aria-label={title}>
          {bins.map((bin) => (
            <div key={bin.center} className="bar-col">
              <div
                className="bar"
                style={{ height: `${(bin.count / maxCount) * 100}%` }}
                title={`${bin.center.toFixed(2)} Hz: ${bin.count}`}
              />
              <span className="bar-label">{bin.center.toFixed(1)}</span>
            </div>
          ))}
        </div>
      )}
      <p className="chart-axis muted">周波数 (Hz)</p>
    </div>
  );
}
