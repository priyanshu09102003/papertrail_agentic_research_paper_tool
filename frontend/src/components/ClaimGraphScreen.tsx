'use client';

import React from 'react';
import { ClaimGraphViewer } from '@/components/ClaimGraphViewer';

interface ClaimGraphScreenProps {
  projectId: string;
  projectName?: string;
}

export function ClaimGraphScreen({ projectId, projectName }: ClaimGraphScreenProps) {
  return (
    <div className="space-y-4 animate-fadeIn">
      <ClaimGraphViewer projectId={projectId} projectName={projectName} />
    </div>
  );
}
