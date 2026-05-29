
import { useEffect, useRef } from 'react';
import { t } from '../i18n';
import { Trash2 } from 'lucide-react';
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
        <span className="context-menu-icon"><Trash2 size={14} /></span>
        {t('sidebar.delete')}
      </button>
    </div>
  );
}

