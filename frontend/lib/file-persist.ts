/**
 * IndexedDB file persistence for surviving page reloads.
 *
 * Stores file metadata + the File blob so the user can continue
 * after an unexpected reload on weak Android devices.
 */

const DB_NAME = 'hearbeat';
const DB_VERSION = 1;
const STORE_NAME = 'files';
const META_KEY = 'selected_file';

export interface PersistedFileMeta {
  name: string;
  size: number;
  type: string;
  lastModified: number;
  storedAt: number;
}

function openDB(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    if (typeof indexedDB === 'undefined') {
      resolve(null);
      return;
    }
    try {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

/**
 * Store a File blob and its metadata in IndexedDB.
 */
export async function persistFile(file: File): Promise<boolean> {
  const db = await openDB();
  if (!db) return false;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);

      const meta: PersistedFileMeta = {
        name: file.name,
        size: file.size,
        type: file.type,
        lastModified: file.lastModified,
        storedAt: Date.now(),
      };

      // Store metadata under a known key
      store.put(meta, META_KEY);
      // Store the file blob under a separate key
      store.put(file, 'file_blob');

      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
    } catch {
      resolve(false);
    }
  });
}

/**
 * Retrieve the persisted file metadata (no blob).
 */
export async function getPersistedMeta(): Promise<PersistedFileMeta | null> {
  const db = await openDB();
  if (!db) return null;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.get(META_KEY);
      req.onsuccess = () => resolve(req.result ?? null);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

/**
 * Retrieve the persisted File blob.
 */
export async function getPersistedBlob(): Promise<File | null> {
  const db = await openDB();
  if (!db) return null;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.get('file_blob');
      req.onsuccess = () => {
        const result = req.result;
        if (result instanceof File) {
          resolve(result);
        } else if (result instanceof Blob) {
          // Reconstruct as File if browser returned a plain Blob
          resolve(new File([result], 'unknown', { type: result.type }));
        } else {
          resolve(null);
        }
      };
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

/**
 * Clear persisted file data from IndexedDB.
 */
export async function clearPersistedFile(): Promise<void> {
  const db = await openDB();
  if (!db) return;

  return new Promise((resolve) => {
    try {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      store.delete(META_KEY);
      store.delete('file_blob');
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
    } catch {
      resolve();
    }
  });
}

/**
 * Attempt to restore a full File from IndexedDB.
 * Returns null if unavailable or if the blob is corrupted.
 */
export async function restoreFile(): Promise<File | null> {
  const meta = await getPersistedMeta();
  if (!meta) return null;

  const blob = await getPersistedBlob();
  if (!blob) return null;

  // Verify the blob matches the metadata
  if (blob.size !== meta.size) {
    await clearPersistedFile();
    return null;
  }

  // Reconstruct a proper File with correct metadata
  return new File([blob], meta.name, {
    type: meta.type || 'audio/mpeg',
    lastModified: meta.lastModified,
  });
}
