"""
ai_analyzer.py — Generates human-readable analysis of comparison results
using the Anthropic Claude API (no API key required in this environment).
"""

import json
import requests
from typing import Dict, Any


def analyze_with_claude(results: Dict[str, Any]) -> str:
    """
    Send comparison results to Claude and get a human-readable explanation
    with recommendations.
    """

    # Build a concise summary of issues for the prompt
    issues_summary = {
        "header_match":     results.get("header_match", "Unknown"),
        "footer_match":     results.get("footer_match", "Unknown"),
        "content_issues":   results.get("content_issues", 0),
        "layout_issues":    results.get("layout_issues", 0),
        "font_differences": results.get("font_diff", "Unknown"),
        "similarity_score": results.get("similarity_score", 0),
        "overall_result":   results.get("overall_result", "Unknown"),
        "sample_diffs": [
            d["text"] for d in results.get("text_diffs", [])[:10]
        ],
    }

    prompt = f"""You are an expert document QA analyst reviewing the results of an automated 
comparison between a template letter and a generated letter in a Collectors module.

Here are the comparison results:
{json.dumps(issues_summary, indent=2)}

Please provide:
1. A clear, concise explanation of what issues were found (2-3 sentences)
2. The most critical problem that needs fixing first
3. Specific, actionable recommendations to fix each issue
4. An overall quality assessment (1 sentence)

Format your response in clear sections. Be direct and technical."""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        data = response.json()

        if "content" in data and data["content"]:
            text_blocks = [b["text"] for b in data["content"] if b.get("type") == "text"]
            return "\n\n".join(text_blocks) if text_blocks else "No analysis returned."

        # Surface API error details
        if "error" in data:
            return f"API Error: {data['error'].get('message', 'Unknown error')}"

        return "Analysis unavailable — unexpected response format."

    except requests.exceptions.Timeout:
        return "Analysis timed out. Please try again."
    except Exception as e:
        return f"Analysis unavailable: {str(e)}"
