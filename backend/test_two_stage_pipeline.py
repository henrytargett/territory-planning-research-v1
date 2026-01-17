#!/usr/bin/env python3
"""
Test script for 2-stage LLM pipeline.

Usage:
    python test_two_stage_pipeline.py "Company Name"

Example:
    python test_two_stage_pipeline.py "Read AI"
"""

import asyncio
import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models import Company, ResearchJob, JobStatus, CompanyStatus
from app.services.research import ResearchPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_company(company_name: str):
    """Test the 2-stage pipeline on a single company."""

    logger.info("=" * 80)
    logger.info(f"Testing 2-Stage Pipeline on: {company_name}")
    logger.info("=" * 80)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Create database session
    db = SessionLocal()

    try:
        # Create a test job
        logger.info("Creating test job...")
        job = ResearchJob(
            name=f"Test Job - {company_name}",
            status=JobStatus.RUNNING.value,
            total_companies=1,
            started_at=datetime.utcnow(),
            submitted_by="test_script"
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"✓ Created job #{job.id}")

        # Create company record
        logger.info(f"Creating company record for: {company_name}")
        company = Company(
            job_id=job.id,
            name=company_name,
            status=CompanyStatus.PENDING.value
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        logger.info(f"✓ Created company #{company.id}")

        # Initialize pipeline
        logger.info("Initializing research pipeline...")
        pipeline = ResearchPipeline()

        # Process company through 2-stage pipeline
        logger.info("")
        logger.info("=" * 80)
        logger.info("STARTING 2-STAGE PIPELINE")
        logger.info("=" * 80)
        logger.info("")

        start_time = datetime.utcnow()
        success = await pipeline.process_company(company, db)
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        logger.info("")
        logger.info("=" * 80)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 80)

        if success:
            # Refresh to get latest data
            db.refresh(company)

            logger.info(f"✓ SUCCESS - Completed in {duration:.2f}s")
            logger.info("")
            logger.info("RESULTS:")
            logger.info(f"  Status: {company.status}")
            logger.info(f"  Tier: {company.gpu_use_case_tier}")
            logger.info(f"  Label: {company.gpu_use_case_label}")
            logger.info(f"  Score: {company.score_total}/100")
            logger.info(f"  Priority: {company.priority_tier}")
            logger.info("")
            logger.info("STAGE TIMESTAMPS:")
            logger.info(f"  Extraction: {company.extraction_timestamp}")
            logger.info(f"  Classification: {company.classification_timestamp}")
            logger.info(f"  Validation: {company.validation_timestamp}")
            logger.info("")
            logger.info("VALIDATION:")
            if company.validation_result:
                validation = company.validation_result
                logger.info(f"  Valid: {validation.get('valid', 'N/A')}")
                logger.info(f"  Needs Review: {validation.get('needs_human_review', 'N/A')}")
                logger.info(f"  Issues: {len(validation.get('issues', []))}")
                if validation.get('issues'):
                    logger.info("  Issue Details:")
                    for issue in validation['issues']:
                        logger.info(f"    - [{issue['severity']}] {issue['type']}: {issue['message']}")
            else:
                logger.info("  No validation data")
            logger.info("")
            logger.info("COSTS:")
            logger.info(f"  Tavily Credits: {company.tavily_credits_used:.4f}")
            logger.info(f"  LLM Tokens: {company.llm_tokens_used}")
            logger.info(f"  Tavily Time: {company.tavily_response_time:.2f}s")
            logger.info(f"  LLM Time: {company.llm_response_time:.2f}s")
            logger.info("")

            # Show reasoning trace if available
            if company.reasoning_trace:
                import json
                reasoning = json.loads(company.reasoning_trace)
                logger.info("REASONING TRACE:")
                for i, step in enumerate(reasoning, 1):
                    logger.info(f"  {i}. {step}")
                logger.info("")

            # Show evidence citations
            if company.classification_result:
                citations = company.classification_result.get('evidence_citations', {})
                if citations:
                    logger.info("EVIDENCE CITATIONS:")
                    for key, value in citations.items():
                        if value:
                            logger.info(f"  {key}: {value}")
                    logger.info("")

            logger.info("=" * 80)
            logger.info(f"✓ Test completed successfully for {company_name}")
            logger.info("=" * 80)

        else:
            logger.error(f"✗ FAILED - Error: {company.error_message}")
            logger.error(f"  Duration: {duration:.2f}s")

        # Update job status
        job.status = JobStatus.COMPLETED.value if success else JobStatus.FAILED.value
        job.completed_at = datetime.utcnow()
        job.completed_companies = 1 if success else 0
        job.failed_companies = 0 if success else 1
        db.commit()

        return success

    except Exception as e:
        logger.error(f"Test failed with exception: {str(e)}", exc_info=True)
        return False

    finally:
        db.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_two_stage_pipeline.py 'Company Name'")
        print("Example: python test_two_stage_pipeline.py 'Read AI'")
        sys.exit(1)

    company_name = sys.argv[1]

    # Run the test
    success = asyncio.run(test_company(company_name))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
