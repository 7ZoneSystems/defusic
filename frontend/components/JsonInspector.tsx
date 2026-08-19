'use client';

import { useState, useMemo } from 'react';
import { Copy, Download, Code } from 'lucide-react';
import { AnalysisResult } from '@/lib/types';

interface JsonInspectorProps {
  result: AnalysisResult;
}

export default function JsonInspector({ result }: JsonInspectorProps) {
  const [copied, setCopied] = useState(false);

  const jsonString = useMemo(
    () => JSON.stringify(result, null, 2),
    [result]
  );

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.source.filename.replace(/\.[^.]+$/, '')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="panel flex flex-col">
      <div className="flex items-center justify-between px-3 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Code size={12} style={{ color: 'var(--text-muted)' }} />
          <span
            className="text-xs uppercase tracking-wider"
            style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-geist-mono)' }}
          >
            JSON
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 text-xs"
            style={{
              color: copied ? 'var(--success)' : 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            <Copy size={10} />
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1 px-2 py-1 text-xs"
            style={{
              color: 'var(--text-muted)',
              border: '1px solid var(--border)',
              borderRadius: '2px',
              fontFamily: 'var(--font-geist-mono)',
            }}
          >
            <Download size={10} />
            Download
          </button>
        </div>
      </div>
      <pre
        className="overflow-auto p-3 text-xs leading-relaxed"
        style={{
          maxHeight: '400px',
          color: 'var(--text-secondary)',
          fontFamily: 'var(--font-geist-mono)',
          background: 'var(--bg-panel)',
        }}
      >
        <code>{jsonString}</code>
      </pre>
    </div>
  );
}
