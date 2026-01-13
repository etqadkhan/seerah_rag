"""
HuggingFace Data Loader Module

This module handles loading the cleaned Seerah transcript data from HuggingFace.
Dataset: rwmasood/transcirpt-seerah-dr-yasir-qadhi

The cleaned transcripts are much better quality than YouTube auto-captions,
providing cleaner text for embedding and retrieval.

Usage:
    python -m data_pipeline.hf_data_loader
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from datasets import load_dataset


# HuggingFace dataset identifier
HF_DATASET_ID = "rwmasood/transcirpt-seerah-dr-yasir-qadhi"


def load_seerah_dataset(split: str = "train") -> list[dict]:
    """
    Load the Seerah transcript dataset from HuggingFace.
    
    Args:
        split: Dataset split to load (default: "train")
        
    Returns:
        List of transcript dictionaries with lecture content
    """
    print(f"Loading dataset from HuggingFace: {HF_DATASET_ID}")
    
    try:
        dataset = load_dataset(HF_DATASET_ID, split=split)
        print(f"Loaded {len(dataset)} entries from dataset")
        return list(dataset)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        raise


def get_transcript_text(entry: dict) -> str:
    """
    Extract clean transcript text from a dataset entry.
    
    The HuggingFace dataset has 'text' column with the transcript.
    
    Args:
        entry: Single entry from the dataset
        
    Returns:
        Clean transcript text
    """
    return str(entry.get('text', '')).strip()


def get_lecture_metadata(entry: dict, index: int) -> dict:
    """
    Extract metadata from a dataset entry.
    
    The 'lecture' field format: "Seerah X - Title - Speaker | Date-VIDEO_ID"
    Example: "Seerah 1 - Specialities of Prophet Muhammad - Yasir Qadhi _ April 2011-VOUp3ZZ9t3A"
    
    Args:
        entry: Single entry from the dataset
        index: Position in the dataset (1-indexed for lecture number)
        
    Returns:
        Dictionary with lecture metadata
    """
    import re
    
    lecture_field = entry.get('lecture', '')
    
    # Default values
    title = f"Seerah Lecture {index}"
    lecture_num = index
    video_id = ""
    
    if lecture_field:
        # Extract video ID from the end (after the last hyphen)
        # Format: "Title-VIDEO_ID"
        parts = lecture_field.rsplit('-', 1)
        if len(parts) == 2 and len(parts[1]) == 11:
            # YouTube video IDs are 11 characters
            video_id = parts[1]
            title = parts[0].strip()
        else:
            title = lecture_field
        
        # Try to extract lecture number from the title
        # Format: "Seerah X - ..."
        match = re.search(r'Seerah\s+(\d+)', title)
        if match:
            lecture_num = int(match.group(1))
        
        # Clean up title - remove redundant "Seerah X -" prefix if we already have number
        clean_match = re.match(r'Seerah\s+\d+\s*[-–]\s*(.+)', title)
        if clean_match:
            title = f"Lecture {lecture_num}: {clean_match.group(1).strip()}"
    
    return {
        'title': title,
        'lecture_number': lecture_num,
        'video_id': video_id,
    }


def process_dataset_for_embedding() -> list[dict]:
    """
    Load and process the HuggingFace dataset for embedding.
    
    Returns:
        List of processed transcript dictionaries ready for chunking.
        Each dictionary contains:
        - title: Lecture title
        - lecture_number: Position in series
        - video_id: YouTube video ID (if available)
        - text: Full transcript text
    """
    # Load the dataset
    raw_data = load_seerah_dataset()
    
    processed = []
    
    for i, entry in enumerate(raw_data, start=1):
        # Get text content
        text = get_transcript_text(entry)
        
        if not text or len(text) < 100:
            print(f"  Skipping entry {i}: insufficient text content")
            continue
        
        # Get metadata
        metadata = get_lecture_metadata(entry, i)
        
        processed.append({
            'title': metadata['title'],
            'lecture_number': metadata['lecture_number'],
            'video_id': metadata['video_id'],
            'text': text,
        })
        
        print(f"  Processed lecture {metadata['lecture_number']}: {metadata['title'][:50]}...")
    
    print(f"\nTotal lectures processed: {len(processed)}")
    return processed


def inspect_dataset() -> dict:
    """
    Inspect the dataset structure and return information about columns.
    
    Returns:
        Dictionary with dataset information
    """
    print(f"Inspecting dataset: {HF_DATASET_ID}")
    
    dataset = load_dataset(HF_DATASET_ID, split="train")
    
    info = {
        'num_entries': len(dataset),
        'columns': list(dataset.column_names) if hasattr(dataset, 'column_names') else [],
        'sample_entry': dict(dataset[0]) if len(dataset) > 0 else {},
    }
    
    print(f"\nDataset Info:")
    print(f"  Entries: {info['num_entries']}")
    print(f"  Columns: {info['columns']}")
    
    if info['sample_entry']:
        print(f"\nSample Entry Keys: {list(info['sample_entry'].keys())}")
        for key, value in info['sample_entry'].items():
            preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            print(f"  {key}: {preview}")
    
    return info


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Main entry point for data loading inspection."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Load and inspect Seerah transcripts from HuggingFace'
    )
    parser.add_argument(
        '--inspect',
        action='store_true',
        help='Inspect dataset structure without processing'
    )
    parser.add_argument(
        '--process',
        action='store_true',
        help='Process dataset for embedding'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("HuggingFace Seerah Transcript Loader")
    print("=" * 60)
    
    if args.inspect:
        inspect_dataset()
    elif args.process:
        transcripts = process_dataset_for_embedding()
        print(f"\nReady for embedding: {len(transcripts)} lectures")
    else:
        # Default: inspect
        inspect_dataset()


if __name__ == "__main__":
    main()
