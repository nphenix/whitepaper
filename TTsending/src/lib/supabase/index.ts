/**
 * Supabase Client for White Paper Generator
 * 
 * Provides database operations for:
 * - User authentication
 * - Search history storage
 * - Project management
 * - Document metadata
 * 
 * Usage:
 * ```typescript
 * import { supabase, saveSearchHistory } from '@/lib/supabase';
 * 
 * // Save a search to history
 * await saveSearchHistory('user-id', 'query', 'response');
 * ```
 */

// ============================================
// Types
// ============================================

export interface SearchHistoryRecord {
  id?: string;
  user_id: string;
  query: string;
  response: string;
  source: 'knowledge' | 'history' | 'web';
  references?: string[];
  created_at?: string;
}

export interface ProjectRecord {
  id?: string;
  user_id: string;
  title: string;
  outline?: string;
  draft?: string;
  status: 'draft' | 'in_progress' | 'completed';
  created_at?: string;
  updated_at?: string;
}

export interface DocumentRecord {
  id?: string;
  project_id?: string;
  external_doc_id?: string;
  filename: string;
  file_path?: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'indexed' | 'failed';
  created_at?: string;
}

// ============================================
// Supabase Client Setup
// ============================================

// Check if we're in browser environment
const isBrowser = typeof window !== 'undefined';

// Get environment variables
const SUPABASE_URL = isBrowser 
  ? (import.meta.env?.VITE_SUPABASE_URL || '') 
  : (process.env?.SUPABASE_URL || '');

const SUPABASE_ANON_KEY = isBrowser 
  ? (import.meta.env?.VITE_SUPABASE_ANON_KEY || '') 
  : (process.env?.SUPABASE_ANON_KEY || '');

/**
 * Simple Supabase client wrapper
 * Uses fetch API for compatibility without requiring @supabase/supabase-js
 */
class SupabaseClient {
  private url: string;
  private key: string;
  private headers: Record<string, string>;

  constructor(url: string, key: string) {
    this.url = url;
    this.key = key;
    this.headers = {
      'apikey': key,
      'Authorization': `Bearer ${key}`,
      'Content-Type': 'application/json',
      'Prefer': 'return=representation',
    };
  }

  /**
   * Check if Supabase is configured
   */
  isConfigured(): boolean {
    return Boolean(this.url && this.key);
  }

  /**
   * Make a request to Supabase REST API
   */
  private async request<T>(
    table: string,
    method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
    options: {
      query?: string;
      body?: unknown;
    } = {}
  ): Promise<{ data: T | null; error: Error | null }> {
    if (!this.isConfigured()) {
      return { 
        data: null, 
        error: new Error('Supabase not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY') 
      };
    }

    try {
      const url = `${this.url}/rest/v1/${table}${options.query ? `?${options.query}` : ''}`;
      
      const response = await fetch(url, {
        method,
        headers: this.headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Supabase error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      return { data, error: null };
    } catch (error) {
      return { 
        data: null, 
        error: error instanceof Error ? error : new Error('Unknown error') 
      };
    }
  }

  /**
   * Select records from a table
   */
  async select<T>(
    table: string,
    options: {
      columns?: string;
      filter?: string;
      order?: string;
      limit?: number;
    } = {}
  ): Promise<{ data: T[] | null; error: Error | null }> {
    const queryParts: string[] = [];
    
    if (options.columns) {
      queryParts.push(`select=${options.columns}`);
    }
    if (options.filter) {
      queryParts.push(options.filter);
    }
    if (options.order) {
      queryParts.push(`order=${options.order}`);
    }
    if (options.limit) {
      queryParts.push(`limit=${options.limit}`);
    }

    return this.request<T[]>(table, 'GET', { 
      query: queryParts.join('&') 
    });
  }

  /**
   * Insert a record into a table
   */
  async insert<T>(
    table: string,
    data: Partial<T>
  ): Promise<{ data: T | null; error: Error | null }> {
    const result = await this.request<T[]>(table, 'POST', { body: data });
    return { 
      data: result.data?.[0] || null, 
      error: result.error 
    };
  }

  /**
   * Update records in a table
   */
  async update<T>(
    table: string,
    data: Partial<T>,
    filter: string
  ): Promise<{ data: T | null; error: Error | null }> {
    const result = await this.request<T[]>(table, 'PATCH', { 
      query: filter,
      body: data 
    });
    return { 
      data: result.data?.[0] || null, 
      error: result.error 
    };
  }

  /**
   * Delete records from a table
   */
  async delete(
    table: string,
    filter: string
  ): Promise<{ error: Error | null }> {
    const result = await this.request(table, 'DELETE', { query: filter });
    return { error: result.error };
  }
}

// Export singleton client
export const supabase = new SupabaseClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// ============================================
// Search History Functions
// ============================================

/**
 * Save a search query and response to history
 */
export async function saveSearchHistory(
  userId: string,
  query: string,
  response: string,
  source: 'knowledge' | 'history' | 'web' = 'knowledge',
  references?: string[]
): Promise<{ data: SearchHistoryRecord | null; error: Error | null }> {
  return supabase.insert<SearchHistoryRecord>('search_history', {
    user_id: userId,
    query,
    response,
    source,
    references,
  });
}

/**
 * Get search history for a user
 */
export async function getSearchHistory(
  userId: string,
  limit: number = 20
): Promise<{ data: SearchHistoryRecord[] | null; error: Error | null }> {
  return supabase.select<SearchHistoryRecord>('search_history', {
    filter: `user_id=eq.${userId}`,
    order: 'created_at.desc',
    limit,
  });
}

/**
 * Delete a search history record
 */
export async function deleteSearchHistory(
  id: string
): Promise<{ error: Error | null }> {
  return supabase.delete('search_history', `id=eq.${id}`);
}

// ============================================
// Project Functions
// ============================================

/**
 * Create a new project
 */
export async function createProject(
  userId: string,
  title: string
): Promise<{ data: ProjectRecord | null; error: Error | null }> {
  return supabase.insert<ProjectRecord>('projects', {
    user_id: userId,
    title,
    status: 'draft',
  });
}

/**
 * Get all projects for a user
 */
export async function getProjects(
  userId: string
): Promise<{ data: ProjectRecord[] | null; error: Error | null }> {
  return supabase.select<ProjectRecord>('projects', {
    filter: `user_id=eq.${userId}`,
    order: 'updated_at.desc',
  });
}

/**
 * Update a project
 */
export async function updateProject(
  projectId: string,
  updates: Partial<ProjectRecord>
): Promise<{ data: ProjectRecord | null; error: Error | null }> {
  return supabase.update<ProjectRecord>('projects', updates, `id=eq.${projectId}`);
}

/**
 * Delete a project
 */
export async function deleteProject(
  projectId: string
): Promise<{ error: Error | null }> {
  return supabase.delete('projects', `id=eq.${projectId}`);
}

// ============================================
// Document Functions
// ============================================

/**
 * Save document metadata
 */
export async function saveDocument(
  doc: Omit<DocumentRecord, 'id' | 'created_at'>
): Promise<{ data: DocumentRecord | null; error: Error | null }> {
  return supabase.insert<DocumentRecord>('documents', doc);
}

/**
 * Get documents for a project
 */
export async function getProjectDocuments(
  projectId: string
): Promise<{ data: DocumentRecord[] | null; error: Error | null }> {
  return supabase.select<DocumentRecord>('documents', {
    filter: `project_id=eq.${projectId}`,
    order: 'created_at.desc',
  });
}

/**
 * Update document status
 */
export async function updateDocumentStatus(
  docId: string,
  status: DocumentRecord['status'],
  externalDocId?: string
): Promise<{ data: DocumentRecord | null; error: Error | null }> {
  const updates: Partial<DocumentRecord> = { status };
  if (externalDocId) {
    updates.external_doc_id = externalDocId;
  }
  return supabase.update<DocumentRecord>('documents', updates, `id=eq.${docId}`);
}

export default supabase;


