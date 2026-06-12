import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import './index.css';

interface DataPreviewModalProps {
  database: string;
  table: string;
  columns: string[];
  rows: any[][];
  onClose: () => void;
}

export default function DataPreviewModal({ database, table, columns, rows, onClose }: DataPreviewModalProps) {
  return createPortal(
    <div className="preview-modal-overlay" onClick={onClose}>
      <div className="preview-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="preview-modal-header">
          <div className="preview-modal-title">
            <span>{table}</span>
            <span className="preview-modal-subtitle">in {database} (Preview top 50 rows)</span>
          </div>
          <button className="preview-modal-close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        
        <div className="preview-modal-body">
          {rows.length === 0 ? (
            <div className="preview-empty">Table is empty</div>
          ) : (
            <div className="preview-table-wrapper">
              <table className="preview-table">
                <thead>
                  <tr>
                    {columns.map((col, idx) => (
                      <th key={idx}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rIdx) => (
                    <tr key={rIdx}>
                      {row.map((cell, cIdx) => (
                        <td key={cIdx}>{cell === null ? <span className="null-val">NULL</span> : String(cell)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
