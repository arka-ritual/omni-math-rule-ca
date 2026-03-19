"""
SWE-bench Pro Dataset Loader

Handles loading SWE-bench Pro dataset from HuggingFace Parquet or JSONL format.
"""

import json
from typing import List, Dict, Any
from pathlib import Path


def load_swe_dataset(file_path: str) -> List[Dict[str, Any]]:
    """
    Load SWE-bench dataset from JSONL file.

    Args:
        file_path: Path to JSONL file

    Returns:
        List of problem dictionaries
    """
    data = []
    with open(file_path, 'r') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def load_swe_dataset_from_hf(split: str = 'test') -> List[Dict[str, Any]]:
    """
    Load SWE-bench dataset directly from HuggingFace.

    Args:
        split: Dataset split to load (default: 'test')

    Returns:
        List of problem dictionaries
    """
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "HuggingFace datasets library required. "
            "Install with: pip install datasets"
        )

    dataset = load_dataset('ScaleAI/SWE-bench_Pro', split=split)
    return list(dataset)


def save_dataset_to_jsonl(data: List[Dict[str, Any]], output_path: str):
    """
    Save dataset to JSONL format.

    Args:
        data: List of problem dictionaries
        output_path: Path to output JSONL file
    """
    with open(output_path, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')


def create_subset(
    data: List[Dict[str, Any]],
    num_samples: int,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """
    Create a deterministic random subset of the dataset.

    Args:
        data: Full dataset
        num_samples: Number of samples to select
        seed: Random seed for reproducibility

    Returns:
        Subset of dataset
    """
    import random
    rng = random.Random(seed)
    indices = sorted(rng.sample(range(len(data)), min(num_samples, len(data))))
    return [data[i] for i in indices]


def format_problem_for_inference(problem: Dict[str, Any]) -> str:
    """
    Format a SWE-bench problem for model input.

    Args:
        problem: Problem dictionary

    Returns:
        Formatted problem string
    """
    repo = problem.get('repo', 'Unknown')
    problem_statement = problem.get('problem_statement', '')

    return f"Repository: {repo}\n\n{problem_statement}"


if __name__ == "__main__":
    # Example usage: Download and create 100-problem subset
    import sys

    if len(sys.argv) < 2:
        print("Usage: python swe_dataset_loader.py <output_path> [num_samples]")
        print("Example: python swe_dataset_loader.py swe_bench_pro_100.jsonl 100")
        sys.exit(1)

    output_path = sys.argv[1]
    num_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    print(f"Loading SWE-bench Pro dataset from HuggingFace...")
    data = load_swe_dataset_from_hf()
    print(f"Loaded {len(data)} problems")

    print(f"Creating subset of {num_samples} problems with seed 42...")
    subset = create_subset(data, num_samples, seed=42)

    print(f"Saving to {output_path}...")
    save_dataset_to_jsonl(subset, output_path)
    print(f"Done! Saved {len(subset)} problems")
