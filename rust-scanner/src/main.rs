//! CodeDNA Fast Scanner - Rust implementation
//! 
//! Design Notes:
//! - Per ADR-002: Subprocess IPC model with stdin/stdout JSON protocol
//! - Baseline comparison is handled by the Python daemon (scanner_client.py)
//!   which has accurate AST parsing and direct database access
//! - This scanner provides fast feature extraction using pattern matching
//! - The daemon passes baseline_vector directly when comparison is needed
//! - For production with Rust-based comparison, consider tree-sitter integration

use serde::{Deserialize, Serialize};
use std::io::{self, BufRead, Write};
use std::time::Instant;

const VECTOR_DIMS: usize = 32;

/// Maximum content size to process (1MB)
const MAX_CONTENT_SIZE: usize = 1_048_576;

/// Scan request from Python daemon
#[derive(Debug, Deserialize)]
struct ScanRequest {
    #[serde(rename = "type")]
    request_type: String,
    language: String,
    content: String,
    #[serde(rename = "fingerprint_id")]
    fingerprint_id: Option<String>,
    #[serde(rename = "baseline_vector")]
    baseline_vector: Option<Vec<f32>>,
    #[serde(rename = "file_path")]
    file_path: Option<String>,
}

/// Scan response to Python daemon
#[derive(Debug, Serialize)]
struct ScanResponse {
    score: Option<f32>,
    #[serde(rename = "partial_vector")]
    partial_vector: Option<Vec<f32>>,
    #[serde(rename = "latency_ms")]
    latency_ms: f32,
    error: Option<String>,
    degraded: bool,
}

impl ScanResponse {
    fn degraded(error: &str, latency_ms: f32) -> Self {
        Self { 
            score: None, 
            partial_vector: None, 
            latency_ms, 
            error: Some(error.to_string()),
            degraded: true,
        }
    }
    fn success(score: f32, vector: Vec<f32>, latency_ms: f32) -> Self {
        Self { 
            score: Some(score), 
            partial_vector: Some(vector), 
            latency_ms, 
            error: None,
            degraded: false,
        }
    }
}

/// Compute cosine similarity between two vectors
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.5;
    }
    
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let mag_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mag_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    
    if mag_a == 0.0 || mag_b == 0.0 {
        return 0.5;
    }
    
    (dot / (mag_a * mag_b)).max(0.0).min(1.0)
}

/// Compute DNA score based on baseline comparison
/// 
/// Uses cosine similarity to compare target vector against baseline.
fn compute_baseline_score(target: &[f32], baseline: &[f32]) -> f32 {
    let similarity = cosine_similarity(target, baseline);
    // Scale similarity [0, 1] to DNA score [0.5, 1.0]
    // Perfect match (1.0) = 1.0 DNA score
    // No match (0.0) = 0.5 DNA score
    (0.5 + similarity * 0.5).min(1.0).max(0.5)
}

/// Compute score based on local variance (fallback when no baseline)
fn compute_variance_score(vector: &[f32]) -> f32 {
    let mean: f32 = vector.iter().sum::<f32>() / vector.len() as f32;
    let variance: f32 = vector.iter().map(|v| (v - mean).powi(2)).sum::<f32>() / vector.len() as f32;
    let score = 0.7 + (variance * 2.0).min(0.25);
    score.min(1.0).max(0.5)
}

/// Extract features from Python source code using pattern matching
/// 
/// Note: This is a fast heuristic-based extraction. For accurate AST-based
/// features, the Python extractor is used. This Rust scanner provides quick
/// feature extraction for sub-100ms scanning requirements.
fn extract_features(content: &str) -> Vec<f32> {
    let mut vector = vec![0.0f32; VECTOR_DIMS];
    
    // Early exit for empty content
    if content.is_empty() {
        return vector;
    }
    
    let lines: Vec<&str> = content.lines().collect();
    let total_lines = lines.len();
    let total_lines_f = total_lines.max(1) as f32;
    
    // Line-based metrics
    let mut line_lengths = Vec::with_capacity(total_lines);
    let mut blank_lines = 0;
    let mut comment_lines = 0;
    let mut todo_lines = 0;
    
    for line in &lines {
        let trimmed = line.trim();
        let len = line.len();
        line_lengths.push(len);
        
        if trimmed.is_empty() {
            blank_lines += 1;
        } else if trimmed.starts_with('#') {
            comment_lines += 1;
            let lower = trimmed.to_lowercase();
            if lower.contains("todo") || lower.contains("fixme") {
                todo_lines += 1;
            }
        }
    }
    
    // Count definitions
    let def_count = content.matches("def ").count();
    let class_count = content.matches("class ").count();
    let total_defs = def_count + class_count;
    let total_defs_f = total_defs.max(1) as f32;
    
    // Count syntax features
    let decorators = content.matches('@').count();
    let imports = content.matches("import ").count() + content.matches("from ").count();
    let relative_imports = content.matches("from .").count();
    let type_hints = content.matches("-> ").count();
    let async_defs = content.matches("async def ").count();
    let lambdas = content.matches("lambda ").count();
    let comprehensions = content.matches("[x for").count() 
        + content.matches("{k: v for").count() 
        + content.matches("(x for").count();
    let walrus = content.matches(":=").count();
    let fstrings = content.matches("f\"").count() + content.matches("f'").count();
    let with_stmts = content.matches("with ").count();
    let try_blocks = content.matches("try:").count();
    let yields = content.matches("yield ").count();
    let matches = content.matches("match ").count();
    let docstrings = content.matches("\"\"\"").count() + content.matches("'''").count();
    
    // Assignments (for identifier metrics)
    let assignments = content.matches(" = ").count();
    let total_assigns_f = assignments.max(1) as f32;
    
    // Line length stats
    let avg_line_len = if !line_lengths.is_empty() {
        line_lengths.iter().sum::<usize>() as f32 / line_lengths.len() as f32
    } else {
        0.0
    };
    let max_line_len = line_lengths.iter().max().copied().unwrap_or(0) as f32;
    
    // Populate vector (matching Python feature order)
    vector[0] = (content.matches('_').count() as f32 / total_assigns_f).min(1.0); // snake_case_ratio
    vector[1] = (content.matches(" i ").count() as f32 / total_assigns_f).min(1.0); // single_char_var_rate
    vector[2] = 0.0; // abbrev_rate (requires identifier parsing)
    vector[3] = avg_line_len / 50.0; // avg_function_length
    vector[4] = (content.matches("  ").count() as f32 / total_lines_f).min(1.0); // nesting_depth (heuristic)
    vector[5] = class_count as f32 / total_defs_f; // class_ratio
    vector[6] = comprehensions as f32 / total_defs_f; // comprehension_rate
    vector[7] = lambdas as f32 / total_defs_f; // lambda_rate
    vector[8] = decorators as f32 / total_defs_f; // decorator_rate
    vector[9] = try_blocks as f32 / total_defs_f; // try_except_ratio
    vector[10] = 0.0; // bare_except_rate (requires AST)
    vector[11] = 0.0; // assert_rate (requires AST)
    vector[12] = docstrings as f32 / total_defs_f; // docstring_rate
    vector[13] = comment_lines as f32 / total_lines_f; // inline_comment_density
    vector[14] = if comment_lines > 0 { todo_lines as f32 / comment_lines as f32 } else { 0.0 }; // todo_comment_rate
    vector[15] = imports as f32 / imports.max(1) as f32; // stdlib_ratio
    vector[16] = relative_imports as f32 / imports.max(1) as f32; // relative_import_rate
    vector[17] = 0.0; // star_import_rate
    vector[18] = avg_line_len / 100.0; // line_length_avg
    vector[19] = max_line_len / 120.0; // line_length_max
    vector[20] = blank_lines as f32 / total_lines_f; // blank_line_density
    vector[21] = type_hints as f32 / total_defs_f; // type_hint_rate (proxy)
    vector[22] = async_defs as f32 / def_count.max(1) as f32; // async_def_rate
    vector[23] = yields as f32 / total_defs_f; // yield_rate
    vector[24] = matches as f32 / total_defs_f; // match_case_rate
    vector[25] = walrus as f32 / total_defs_f; // walrus_operator_rate
    vector[26] = fstrings as f32 / total_defs_f; // fstring_rate
    vector[27] = fstrings as f32 / total_defs_f; // list_append_in_loop (heuristic)
    vector[28] = content.matches(".get(").count() as f32 / total_defs_f; // dict_get_rate (heuristic)
    vector[29] = with_stmts as f32 / total_defs_f; // context_manager_rate
    vector[30] = 0.0; // generator_rate (requires AST)
    
    // Clamp all values to [0.0, 1.0]
    for v in &mut vector {
        *v = v.clamp(0.0, 1.0);
    }
    
    vector
}

fn main() {
    // Initialize logging (only if RUST_LOG is set)
    if std::env::var("RUST_LOG").is_ok() {
        env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    }
    
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();
    
    while let Some(line) = lines.next() {
        let start = Instant::now();
        match line {
            Ok(raw) if !raw.trim().is_empty() => {
                let response = process_request(&raw);
                let elapsed = start.elapsed().as_secs_f32() * 1000.0;
                let response = match response {
                    Ok(mut resp) => { resp.latency_ms = elapsed; resp }
                    Err(e) => ScanResponse::degraded(&e, elapsed),
                };
                if let Ok(json) = serde_json::to_string(&response) {
                    println!("{}", json);
                    io::stdout().flush().ok();
                }
            }
            Ok(_) => continue,
            Err(_) => break,
        }
    }
}

fn process_request(raw: &str) -> Result<ScanResponse, String> {
    let request: ScanRequest = serde_json::from_str(raw).map_err(|e| format!("Invalid JSON: {}", e))?;
    
    // Validate content size
    if request.content.len() > MAX_CONTENT_SIZE {
        return Err(format!("Content exceeds maximum size of {} bytes", MAX_CONTENT_SIZE));
    }
    
    match request.request_type.as_str() {
        "scan_file" | "scan_diff" => {
            let score = if let Some(baseline) = request.baseline_vector {
                // Use baseline comparison when provided
                let vector = extract_features(&request.content);
                compute_baseline_score(&vector, &baseline)
            } else {
                // Fall back to variance-based scoring
                let vector = extract_features(&request.content);
                compute_variance_score(&vector)
            };
            
            let vector = extract_features(&request.content);
            Ok(ScanResponse::success(score, vector, 0.0))
        }
        _ => Err(format!("Unknown scan type: {}", request.request_type)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_feature_extraction() {
        let content = "def hello():\n    pass\n";
        let vector = extract_features(content);
        assert_eq!(vector.len(), VECTOR_DIMS);
        assert!(vector.iter().all(|v| (0.0..=1.0).contains(&v)));
    }
    
    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 0.001);
        
        let c = vec![0.0, 1.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &c) - 0.0).abs() < 0.001);
    }
    
    #[test]
    fn test_baseline_score() {
        let target = vec![0.5; VECTOR_DIMS];
        let baseline = vec![0.5; VECTOR_DIMS];
        let score = compute_baseline_score(&target, &baseline);
        assert!((score - 1.0).abs() < 0.001);
        
        let different = vec![0.0; VECTOR_DIMS];
        let score_diff = compute_baseline_score(&target, &different);
        assert!(score_diff < 1.0);
    }
    
    #[test]
    fn test_variance_score() {
        let vector = vec![0.5; VECTOR_DIMS];
        let score = compute_variance_score(&vector);
        assert!((0.0..=1.0).contains(&score));
    }
    
    #[test]
    fn test_empty_content() {
        let vector = extract_features("");
        assert_eq!(vector.len(), VECTOR_DIMS);
        assert!(vector.iter().all(|v| *v == 0.0));
    }
}