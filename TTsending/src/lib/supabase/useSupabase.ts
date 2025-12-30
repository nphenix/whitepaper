/**
 * React Hooks for Supabase
 * 
 * Provides easy-to-use hooks for search history and projects.
 * 
 * Usage:
 * ```tsx
 * import { useSearchHistory } from '@/lib/supabase/useSupabase';
 * 
 * function MyComponent() {
 *   const { history, saveSearch, loading } = useSearchHistory('user-id');
 * }
 * ```
 */

import { useState, useEffect, useCallback } from 'react';
import { 
  SearchHistoryRecord, 
  ProjectRecord,
  getSearchHistory, 
  saveSearchHistory,
  getProjects,
  createProject,
  updateProject,
  deleteProject,
  supabase,
} from './index';

// ============================================
// Search History Hook
// ============================================

interface UseSearchHistoryReturn {
  /** Search history records */
  history: SearchHistoryRecord[];
  /** Loading state */
  loading: boolean;
  /** Error state */
  error: Error | null;
  /** Save a new search to history */
  saveSearch: (query: string, response: string, source?: 'knowledge' | 'history' | 'web') => Promise<void>;
  /** Refresh the history */
  refresh: () => Promise<void>;
  /** Whether Supabase is configured */
  isConfigured: boolean;
}

/**
 * Hook for managing search history
 * 
 * @param userId - The user ID (can be anonymous ID for demo)
 * @returns Search history state and functions
 */
export function useSearchHistory(userId?: string): UseSearchHistoryReturn {
  const [history, setHistory] = useState<SearchHistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  // Use provided userId or generate a demo one
  const effectiveUserId = userId || 'demo-user';
  const isConfigured = supabase.isConfigured();

  const refresh = useCallback(async () => {
    if (!isConfigured) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await getSearchHistory(effectiveUserId);
      if (result.error) throw result.error;
      setHistory(result.data || []);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load history'));
    } finally {
      setLoading(false);
    }
  }, [effectiveUserId, isConfigured]);

  const saveSearch = useCallback(async (
    query: string, 
    response: string, 
    source: 'knowledge' | 'history' | 'web' = 'knowledge'
  ) => {
    if (!isConfigured) {
      // Store locally if Supabase is not configured
      const localRecord: SearchHistoryRecord = {
        id: Date.now().toString(),
        user_id: effectiveUserId,
        query,
        response,
        source,
        created_at: new Date().toISOString(),
      };
      setHistory(prev => [localRecord, ...prev]);
      return;
    }

    try {
      const result = await saveSearchHistory(effectiveUserId, query, response, source);
      if (result.error) throw result.error;
      
      // Add to local state
      if (result.data) {
        setHistory(prev => [result.data!, ...prev]);
      }
    } catch (err) {
      console.error('Failed to save search history:', err);
    }
  }, [effectiveUserId, isConfigured]);

  // Load history on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    history,
    loading,
    error,
    saveSearch,
    refresh,
    isConfigured,
  };
}

// ============================================
// Projects Hook
// ============================================

interface UseProjectsReturn {
  /** User's projects */
  projects: ProjectRecord[];
  /** Loading state */
  loading: boolean;
  /** Error state */
  error: Error | null;
  /** Create a new project */
  create: (title: string) => Promise<ProjectRecord | null>;
  /** Update a project */
  update: (projectId: string, updates: Partial<ProjectRecord>) => Promise<void>;
  /** Delete a project */
  remove: (projectId: string) => Promise<void>;
  /** Refresh projects list */
  refresh: () => Promise<void>;
  /** Whether Supabase is configured */
  isConfigured: boolean;
}

/**
 * Hook for managing projects
 * 
 * @param userId - The user ID
 * @returns Projects state and functions
 */
export function useProjects(userId?: string): UseProjectsReturn {
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const effectiveUserId = userId || 'demo-user';
  const isConfigured = supabase.isConfigured();

  const refresh = useCallback(async () => {
    if (!isConfigured) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const result = await getProjects(effectiveUserId);
      if (result.error) throw result.error;
      setProjects(result.data || []);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load projects'));
    } finally {
      setLoading(false);
    }
  }, [effectiveUserId, isConfigured]);

  const create = useCallback(async (title: string): Promise<ProjectRecord | null> => {
    if (!isConfigured) {
      // Create locally
      const localProject: ProjectRecord = {
        id: Date.now().toString(),
        user_id: effectiveUserId,
        title,
        status: 'draft',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setProjects(prev => [localProject, ...prev]);
      return localProject;
    }

    try {
      const result = await createProject(effectiveUserId, title);
      if (result.error) throw result.error;
      
      if (result.data) {
        setProjects(prev => [result.data!, ...prev]);
      }
      return result.data;
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to create project'));
      return null;
    }
  }, [effectiveUserId, isConfigured]);

  const update = useCallback(async (projectId: string, updates: Partial<ProjectRecord>) => {
    if (!isConfigured) {
      setProjects(prev => prev.map(p => 
        p.id === projectId ? { ...p, ...updates } : p
      ));
      return;
    }

    try {
      const result = await updateProject(projectId, updates);
      if (result.error) throw result.error;
      
      setProjects(prev => prev.map(p => 
        p.id === projectId ? { ...p, ...updates } : p
      ));
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to update project'));
    }
  }, [isConfigured]);

  const remove = useCallback(async (projectId: string) => {
    if (!isConfigured) {
      setProjects(prev => prev.filter(p => p.id !== projectId));
      return;
    }

    try {
      const result = await deleteProject(projectId);
      if (result.error) throw result.error;
      
      setProjects(prev => prev.filter(p => p.id !== projectId));
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to delete project'));
    }
  }, [isConfigured]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return {
    projects,
    loading,
    error,
    create,
    update,
    remove,
    refresh,
    isConfigured,
  };
}

export default useSearchHistory;





