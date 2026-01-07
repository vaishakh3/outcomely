"""
CLI entry point for the Finfluencer Tracker.
Provides commands to fetch, extract, verify, and serve.
"""
import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

from config import CREATORS

console = Console()


@click.group()
def cli():
    """Finance YouTuber Prediction Accuracy Tracker"""
    pass


@cli.command()
@click.option('--creator', '-c', help='Creator slug (e.g., akshat, warikoo, rachana)')
@click.option('--all', 'all_creators', is_flag=True, help='Fetch all configured creators')
@click.option('--limit', '-l', default=50, help='Max videos per creator')
def fetch(creator, all_creators, limit):
    """Fetch videos and transcripts from YouTube"""
    from youtube_fetcher import fetch_creator_videos, fetch_all_creators, fetch_transcripts_for_videos
    from database import get_db
    
    # Initialize creators in database
    db = get_db()
    for c in CREATORS:
        db.add_creator(c.name, c.channel_id, c.channel_url, c.slug, c.description or "")
    
    if all_creators:
        console.print("[bold blue]Fetching videos for all creators...[/]")
        fetch_all_creators(limit_per_creator=limit)
    elif creator:
        console.print(f"[bold blue]Fetching videos for {creator}...[/]")
        fetch_creator_videos(creator, limit=limit)
        # Fetch transcripts
        console.print("[bold blue]Fetching transcripts...[/]")
        fetch_transcripts_for_videos(limit=limit)
    else:
        console.print("[red]Please specify --creator or --all[/]")
        return
    
    console.print("[bold green]✓ Fetch complete![/]")


@cli.command()
@click.option('--limit', '-l', default=10, help='Max videos to process')
@click.option('--video-id', '-v', help='Specific video ID to process')
def extract(limit, video_id):
    """Extract predictions from video transcripts"""
    from prediction_extractor import process_unprocessed_videos, extract_predictions_for_video
    
    if video_id:
        console.print(f"[bold blue]Extracting predictions from video {video_id}...[/]")
        predictions = extract_predictions_for_video(video_id)
        console.print(f"[green]Found {len(predictions)} predictions[/]")
    else:
        console.print(f"[bold blue]Processing up to {limit} videos...[/]")
        results = process_unprocessed_videos(limit=limit)
        
        console.print(f"\n[bold green]✓ Extraction complete![/]")
        console.print(f"  Videos processed: {results['videos_processed']}")
        console.print(f"  Predictions extracted: {results['predictions_extracted']}")


@cli.command()
@click.option('--limit', '-l', default=10, help='Max predictions to verify')
@click.option('--prediction-id', '-p', type=int, help='Specific prediction ID to verify')
def verify(limit, prediction_id):
    """Verify predictions against market data"""
    from accuracy_scorer import verify_unverified_predictions, verify_prediction_by_id
    
    if prediction_id:
        console.print(f"[bold blue]Verifying prediction {prediction_id}...[/]")
        result = verify_prediction_by_id(prediction_id)
        
        if result.get('status') == 'verified':
            console.print(f"[green]Score: {result['overall_score']:.1%}[/]")
            console.print(f"Explanation: {result['explanation']}")
        elif result.get('status') == 'pending':
            console.print("[yellow]Prediction timeframe not yet complete[/]")
        else:
            console.print(f"[red]Error: {result.get('message', 'Unknown error')}[/]")
    else:
        console.print(f"[bold blue]Verifying up to {limit} predictions...[/]")
        results = verify_unverified_predictions(limit=limit)
        
        console.print(f"\n[bold green]✓ Verification complete![/]")
        console.print(f"  Verified: {results['verified']}")
        console.print(f"  Pending: {results['pending']}")
        console.print(f"  Errors: {results['errors']}")
        if results['average_score'] > 0:
            console.print(f"  Average score: {results['average_score']:.1%}")


@cli.command()
def score():
    """Recalculate all accuracy scores"""
    from database import get_db
    
    console.print("[bold blue]Recalculating scores...[/]")
    
    db = get_db()
    db.recalculate_creator_scores()
    
    console.print("[bold green]✓ Scores recalculated![/]")


@cli.command()
def leaderboard():
    """Show the current leaderboard"""
    from database import get_db
    
    db = get_db()
    creators = db.get_leaderboard()
    
    if not creators:
        console.print("[yellow]No data yet. Run 'fetch' and 'extract' first.[/]")
        return
    
    table = Table(title="🏆 Finfluencer Accuracy Leaderboard")
    table.add_column("Rank", justify="center", style="cyan")
    table.add_column("Creator", style="bold")
    table.add_column("Accuracy", justify="right", style="green")
    table.add_column("Predictions", justify="right")
    table.add_column("Videos", justify="right")
    
    for i, creator in enumerate(creators, 1):
        score = creator['accuracy_score'] or 0
        score_str = f"{score:.1%}" if score > 0 else "—"
        
        # Color based on score
        if score >= 0.7:
            score_color = "green"
        elif score >= 0.5:
            score_color = "yellow"
        else:
            score_color = "red"
        
        table.add_row(
            str(i),
            creator['name'],
            f"[{score_color}]{score_str}[/]",
            str(creator['total_predictions'] or 0),
            str(creator['video_count'] or 0)
        )
    
    console.print(table)


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', '-p', default=8000, help='Port to bind to')
def serve(host, port):
    """Start the web server"""
    import uvicorn
    
    console.print(f"[bold blue]Starting server at http://{host}:{port}[/]")
    console.print("[dim]Frontend at http://{host}:{port}/[/]")
    console.print("[dim]API at http://{host}:{port}/api/[/]")
    
    uvicorn.run("server:app", host=host, port=port, reload=True)


@cli.command()
def init():
    """Initialize the database with configured creators"""
    from database import get_db
    
    console.print("[bold blue]Initializing database...[/]")
    
    db = get_db()
    
    for creator in CREATORS:
        db.add_creator(
            name=creator.name,
            channel_id=creator.channel_id,
            channel_url=creator.channel_url,
            slug=creator.slug,
            description=creator.description or ""
        )
        console.print(f"  Added: {creator.name}")
    
    console.print("[bold green]✓ Database initialized![/]")


@cli.command()
@click.option('--creator', '-c', help='Creator slug to show details for')
def stats(creator):
    """Show statistics"""
    from database import get_db
    
    db = get_db()
    
    if creator:
        creator_data = db.get_creator_by_slug(creator)
        if not creator_data:
            console.print(f"[red]Creator '{creator}' not found[/]")
            return
        
        predictions = db.get_predictions_by_creator(creator_data['id'])
        
        console.print(f"\n[bold]{creator_data['name']}[/]")
        console.print(f"Channel: {creator_data['channel_url']}")
        console.print(f"Total predictions: {len(predictions)}")
        console.print(f"Accuracy score: {(creator_data['accuracy_score'] or 0):.1%}")
        
        # Show recent predictions
        if predictions:
            console.print("\n[bold]Recent Predictions:[/]")
            for pred in predictions[:5]:
                score = pred.get('overall_score')
                score_str = f"{score:.1%}" if score else "Pending"
                console.print(f"  • {pred['statement'][:60]}... [{score_str}]")
    else:
        # Show overall stats
        creators = db.get_leaderboard()
        
        total_predictions = sum(c['total_predictions'] or 0 for c in creators)
        total_videos = sum(c['video_count'] or 0 for c in creators)
        
        console.print("\n[bold]Overall Statistics[/]")
        console.print(f"  Creators tracked: {len(creators)}")
        console.print(f"  Total videos: {total_videos}")
        console.print(f"  Total predictions: {total_predictions}")


if __name__ == '__main__':
    cli()
