"""
Firebase Cloud Storage Utility for Spoken Wardrobe

Provides cloud storage for GLB mesh files and preview images,
enabling a gallery of all generated creations.

Setup:
1. Create Firebase project at https://console.firebase.google.com/
2. Enable Storage in test mode
3. Download service account JSON from Project Settings > Service Accounts
4. Save as firebase-credentials.json in project root
5. Add to .gitignore to prevent committing credentials

Usage:
    from utils.firebase_storage import CloudStorage

    storage = CloudStorage(
        credentials_path='firebase-credentials.json',
        bucket_name='your-project.firebasestorage.app'
    )

    # Upload mesh
    url = storage.upload_glb('/path/to/mesh.glb', {'prompt': 'a blue dress'})

    # List all meshes for gallery
    meshes = storage.list_all_meshes()
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class CloudStorage:
    """
    Firebase Cloud Storage wrapper for mesh and preview uploads.

    Handles authentication, uploads, and listing of stored assets.
    Falls back gracefully if Firebase is not configured.
    """

    def __init__(self, credentials_path: str, bucket_name: str):
        """
        Initialize Firebase Storage connection.

        Args:
            credentials_path: Path to Firebase service account JSON file
            bucket_name: Storage bucket name (e.g., 'project-id.firebasestorage.app')

        Raises:
            ImportError: If firebase-admin package is not installed
            FileNotFoundError: If credentials file doesn't exist
            Exception: If Firebase initialization fails
        """
        self.credentials_path = credentials_path
        self.bucket_name = bucket_name
        self.bucket = None
        self._initialized = False

        self._initialize()

    def _initialize(self):
        """Initialize Firebase connection."""
        try:
            import firebase_admin
            from firebase_admin import credentials, storage

            # Check if already initialized
            try:
                firebase_admin.get_app()
                self.bucket = storage.bucket()
                self._initialized = True
                return
            except ValueError:
                pass  # Not initialized yet

            # Check credentials file exists
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"Firebase credentials not found: {self.credentials_path}\n"
                    "Download from: Firebase Console > Project Settings > Service Accounts"
                )

            # Initialize Firebase
            cred = credentials.Certificate(self.credentials_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': self.bucket_name
            })

            self.bucket = storage.bucket()
            self._initialized = True

        except ImportError:
            raise ImportError(
                "firebase-admin package not installed.\n"
                "Install with: pip install firebase-admin"
            )

    @property
    def is_available(self) -> bool:
        """Check if Firebase storage is properly configured and available."""
        return self._initialized and self.bucket is not None

    def upload_glb(self, local_path: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Upload a GLB mesh file to cloud storage.

        Args:
            local_path: Path to local GLB file
            metadata: Dict with metadata (prompt, timestamp, etc.)

        Returns:
            Public URL of uploaded file, or None if upload fails
        """
        if not self.is_available:
            print("[CloudStorage] Not available, skipping upload")
            return None

        try:
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            original_name = Path(local_path).stem
            blob_name = f"meshes/{timestamp}_{original_name}.glb"

            # Create blob and upload
            blob = self.bucket.blob(blob_name)

            # Set metadata
            blob.metadata = {
                'prompt': str(metadata.get('prompt', '')),
                'timestamp': str(metadata.get('timestamp', timestamp)),
                'original_filename': str(Path(local_path).name)
            }

            # Upload file
            blob.upload_from_filename(local_path, content_type='model/gltf-binary')

            # Make publicly accessible
            blob.make_public()

            print(f"[CloudStorage] Uploaded: {blob_name}")
            return blob.public_url

        except Exception as e:
            print(f"[CloudStorage] Upload failed: {e}")
            return None

    def upload_preview(self, local_path: str, metadata: Dict[str, Any]) -> Optional[str]:
        """
        Upload a preview image to cloud storage.

        Args:
            local_path: Path to local image file (PNG/JPG)
            metadata: Dict with metadata

        Returns:
            Public URL of uploaded file, or None if upload fails
        """
        if not self.is_available:
            print("[CloudStorage] Not available, skipping upload")
            return None

        try:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            extension = Path(local_path).suffix or '.png'
            blob_name = f"previews/{timestamp}{extension}"

            # Create blob and upload
            blob = self.bucket.blob(blob_name)
            blob.metadata = {
                'prompt': str(metadata.get('prompt', '')),
                'timestamp': str(metadata.get('timestamp', timestamp))
            }

            # Determine content type
            content_type = 'image/png' if extension.lower() == '.png' else 'image/jpeg'
            blob.upload_from_filename(local_path, content_type=content_type)

            blob.make_public()

            print(f"[CloudStorage] Uploaded preview: {blob_name}")
            return blob.public_url

        except Exception as e:
            print(f"[CloudStorage] Preview upload failed: {e}")
            return None

    def list_all_meshes(self) -> List[Dict[str, Any]]:
        """
        Get all mesh URLs and metadata for gallery display.

        Returns:
            List of dicts with 'url' and 'metadata' keys
        """
        if not self.is_available:
            print("[CloudStorage] Not available")
            return []

        try:
            blobs = self.bucket.list_blobs(prefix='meshes/')
            meshes = []

            for blob in blobs:
                if blob.name.endswith('.glb'):
                    # Reload to get metadata
                    blob.reload()
                    meshes.append({
                        'url': blob.public_url,
                        'name': blob.name,
                        'metadata': blob.metadata or {},
                        'created': blob.time_created.isoformat() if blob.time_created else None,
                        'size_kb': blob.size / 1024 if blob.size else 0
                    })

            # Sort by creation time (newest first)
            meshes.sort(key=lambda x: x.get('created', ''), reverse=True)

            print(f"[CloudStorage] Found {len(meshes)} meshes")
            return meshes

        except Exception as e:
            print(f"[CloudStorage] List failed: {e}")
            return []

    def list_all_previews(self) -> List[Dict[str, Any]]:
        """
        Get all preview image URLs and metadata.

        Returns:
            List of dicts with 'url' and 'metadata' keys
        """
        if not self.is_available:
            return []

        try:
            blobs = self.bucket.list_blobs(prefix='previews/')
            previews = []

            for blob in blobs:
                if blob.name.endswith(('.png', '.jpg', '.jpeg')):
                    blob.reload()
                    previews.append({
                        'url': blob.public_url,
                        'name': blob.name,
                        'metadata': blob.metadata or {},
                        'created': blob.time_created.isoformat() if blob.time_created else None
                    })

            previews.sort(key=lambda x: x.get('created', ''), reverse=True)
            return previews

        except Exception as e:
            print(f"[CloudStorage] List previews failed: {e}")
            return []

    def delete_mesh(self, blob_name: str) -> bool:
        """
        Delete a mesh from cloud storage.

        Args:
            blob_name: Name/path of the blob to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.is_available:
            return False

        try:
            blob = self.bucket.blob(blob_name)
            blob.delete()
            print(f"[CloudStorage] Deleted: {blob_name}")
            return True

        except Exception as e:
            print(f"[CloudStorage] Delete failed: {e}")
            return False


def create_storage_if_available() -> Optional[CloudStorage]:
    """
    Factory function to create CloudStorage if credentials are available.

    Looks for firebase-credentials.json in project root.
    Returns None if Firebase is not configured.

    Returns:
        CloudStorage instance or None
    """
    # Find project root (look for CLAUDE.md or .git)
    current = Path(__file__).parent
    for _ in range(5):  # Max 5 levels up
        if (current / 'CLAUDE.md').exists() or (current / '.git').exists():
            break
        current = current.parent

    creds_path = current / 'firebase-credentials.json'

    if not creds_path.exists():
        print("[CloudStorage] No credentials found, cloud storage disabled")
        return None

    try:
        # Read bucket name from credentials
        import json
        with open(creds_path) as f:
            creds = json.load(f)
            project_id = creds.get('project_id', 'spoken-wardrobe')

        bucket_name = f"{project_id}.firebasestorage.app"

        return CloudStorage(str(creds_path), bucket_name)

    except Exception as e:
        print(f"[CloudStorage] Initialization failed: {e}")
        return None
