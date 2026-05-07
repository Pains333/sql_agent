/* ============================================
   ContextMenu — right-click context menu
   ============================================ */

import { useEffect, useRef } from 'react';
import './ContextMenu.css';

interface ContextMenuProps {
  x: number;
  y: number;
  onDelete: () => void;
  onClose: () => void;
}

export default function ContextMenu({ x, y, onDelete, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  return (
    <div className="context-menu" style={{ top: y, left: x }} ref={ref}>
      <button className="context-menu-item danger" onClick={onDelete}>
        <span className="context-menu-icon">🗑️</span>
        删除对话
      </button>
    </div>
  );
}
