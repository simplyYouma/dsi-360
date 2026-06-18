/** Props communes pour les <Tooltip> Recharts : lisibles en clair/sombre et toujours au-dessus. */
export const infobulle = {
  allowEscapeViewBox: { x: false, y: true } as const,
  wrapperStyle: { zIndex: 60, outline: 'none' },
  contentStyle: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    boxShadow: 'var(--shadow-md)',
    color: 'var(--text)',
    fontSize: 13,
  },
  itemStyle: { color: 'var(--text)' },
  labelStyle: { color: 'var(--text-muted)', marginBottom: 2 },
};
