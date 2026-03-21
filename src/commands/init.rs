use anyhow::Result;
use colored::Colorize;
use plugin_store::submission::init;

pub fn execute(name: &str) -> Result<()> {
    let cwd = std::env::current_dir()?;

    println!("Scaffolding plugin '{}'...", name.bold());
    init::scaffold(name, &cwd)?;

    println!("\n{} Created plugin at ./{}/", "✓".green().bold(), name);
    println!("\nNext steps:");
    println!("  1. cd {}/", name);
    println!("  2. Edit plugin.yaml — fill in your details");
    println!("  3. Edit skills/{}/SKILL.md — write your skill", name);
    println!("  4. Run: plugin-store lint ./ ");
    println!("  5. Copy to plugin-store-community/submissions/ and open a PR");

    Ok(())
}
