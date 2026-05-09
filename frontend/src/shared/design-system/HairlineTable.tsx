/**
 * HairlineTable — Editorial data table with 1 px hairline borders.
 *
 * What: A styled table using `--hairline` token for all borders. Zero rounded
 * corners. Uppercase tracked column headers (`TrackedLabel` style). Used for
 * admin data views, audit logs, and user lists.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: instrucciones.md §7 ("HairlineTable"), TECHNICAL_GUIDE §7
 *
 * Logging:
 *   No runtime actions. BEFORE/AFTER logging applies when HairlineTable gains
 *   sort/pagination callbacks in a downstream slice.
 *
 * Accessibility:
 *   - <table> element with role="table" implied.
 *   - Column headers use <th scope="col">.
 *   - caption prop renders a <caption> for screen readers.
 */

import type { CSSProperties, ReactNode } from 'react';

interface Column {
  /** Column key (used as React key). */
  key: string;
  /** Column header label. Rendered uppercase + tracked. */
  header: string;
  /** Column width (CSS value). Optional. */
  width?: string;
}

interface HairlineTableProps {
  /** Column definitions. */
  columns: Column[];
  /** Table rows — each row is a Record matching column keys to ReactNode. */
  rows: Record<string, ReactNode>[];
  /** Accessible caption text for screen readers. */
  caption?: string;
  /** Additional class for outer wrapper. */
  className?: string;
}

const tableStyle: CSSProperties = {
  width:          '100%',
  borderCollapse: 'collapse',
  fontFamily:     'var(--font-sans)',
  fontSize:       'var(--text-sm)',
  color:          'var(--color-text-primary)',
  borderRadius:   'var(--radius)',   /* = 0 */
};

const thStyle: CSSProperties = {
  padding:        'var(--space-3) var(--space-4)',
  textAlign:      'left',
  fontWeight:     'var(--weight-semibold)' as string,
  fontSize:       'var(--text-xs)',
  letterSpacing:  'var(--tracking-label)',
  textTransform:  'uppercase',
  color:          'var(--color-text-secondary)',
  borderBottom:   'var(--hairline)',
  borderRadius:   'var(--radius)',
};

const tdStyle: CSSProperties = {
  padding:      'var(--space-4)',
  borderBottom: 'var(--hairline)',
  color:        'var(--color-text-primary)',
  borderRadius: 'var(--radius)',
};

/**
 * Editorial data table with hairline borders and uppercase tracked headers.
 *
 * @param columns - Column definitions.
 * @param rows - Row data arrays.
 * @param caption - Screen-reader caption.
 * @param className - Layout wrapper class.
 */
export function HairlineTable({ columns, rows, caption, className }: HairlineTableProps) {
  return (
    <div className={className} style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        {caption !== undefined && <caption style={{ display: 'none' }}>{caption}</caption>}
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" style={{ ...thStyle, width: col.width }}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((col) => (
                <td key={col.key} style={tdStyle}>
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
