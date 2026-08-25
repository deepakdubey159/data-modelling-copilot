#!/bin/bash
# AI Data Migration Accelerator - Batch Migration Script
# Runs multiple migrations from different databases/schemas
# Usage: bash batch-migrate.sh

set -e  # Exit on error

echo "=========================================="
echo "Batch Migration - Multiple Databases"
echo "=========================================="
echo ""

# Activate virtual environment
source venv/bin/activate

# Create reports directory
mkdir -p migration-reports

# Initialize tracking file
REPORT_FILE="migration-reports/batch-report-$(date +%Y%m%d_%H%M%S).txt"
echo "=========================================="  > "$REPORT_FILE"
echo "Batch Migration Report"                      >> "$REPORT_FILE"
echo "Started: $(date)"                            >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"
echo ""                                             >> "$REPORT_FILE"

# Define migrations (customize these for your environment)
MIGRATIONS=(
    "config-db2-sales"
    "config-postgres-marketing"
    "config-mysql-analytics"
)

FAILED=0
SUCCEEDED=0
SKIPPED=0

# Run each migration
for migration_name in "${MIGRATIONS[@]}"; do
    CONFIG_FILE="configs/${migration_name}.yaml"

    if [ ! -f "$CONFIG_FILE" ]; then
        echo "⚠️  Skipping $migration_name (config not found)"
        echo "SKIPPED: $migration_name (config not found)"  >> "$REPORT_FILE"
        ((SKIPPED++))
        continue
    fi

    echo ""
    echo "=========================================="
    echo "Running: $migration_name"
    echo "Config: $CONFIG_FILE"
    echo "=========================================="

    START_TIME=$(date +%s)

    # Run migration, capture result
    if python migrate.py --config "$CONFIG_FILE" 2>&1 | tee -a "$REPORT_FILE"; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        echo "✅ COMPLETED: $migration_name (${DURATION}s)"
        echo "COMPLETED: $migration_name (${DURATION}s)" >> "$REPORT_FILE"
        ((SUCCEEDED++))
    else
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        echo "❌ FAILED: $migration_name (${DURATION}s)"
        echo "FAILED: $migration_name (${DURATION}s)" >> "$REPORT_FILE"
        ((FAILED++))
    fi
done

# Print summary
echo ""
echo "=========================================="
echo "Batch Migration Summary"
echo "=========================================="
echo "Succeeded: $SUCCEEDED"
echo "Failed:    $FAILED"
echo "Skipped:   $SKIPPED"
echo "Total:     $((SUCCEEDED + FAILED + SKIPPED))"
echo ""
echo "Report saved to: $REPORT_FILE"
echo "=========================================="

# Add to report file
echo ""                                             >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"
echo "Summary"                                      >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"
echo "Succeeded: $SUCCEEDED"                        >> "$REPORT_FILE"
echo "Failed:    $FAILED"                           >> "$REPORT_FILE"
echo "Skipped:   $SKIPPED"                          >> "$REPORT_FILE"
echo "Total:     $((SUCCEEDED + FAILED + SKIPPED))" >> "$REPORT_FILE"
echo "Ended:     $(date)"                           >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"

# Exit with error if any failed
if [ $FAILED -gt 0 ]; then
    echo ""
    echo "❌ Some migrations failed. Check report: $REPORT_FILE"
    exit 1
else
    echo ""
    echo "✅ All migrations completed successfully!"
    exit 0
fi
