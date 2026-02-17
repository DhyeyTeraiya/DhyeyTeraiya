import os
import requests
import re
from datetime import datetime

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
USERNAME = 'DhyeyTeraiya'

def get_stats():
    query = """
    query($login:String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    response = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': {'login': USERNAME}}, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.status_code}")
        
    data = response.json()['data']['user']['contributionsCollection']['contributionCalendar']
    total_contributions = data['totalContributions']
    
    # Calculate streak
    days = []
    for week in data['weeks']:
        days.extend(week['contributionDays'])
    
    days.reverse() # Start from most recent
    
    streak = 0
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = datetime.now().replace(day=datetime.now().day-1).strftime('%Y-%m-%d')
    
    # Simple streak calculation: count consecutive days with > 0 contributions starting from today or yesterday
    finding_streak = False
    for day in days:
        if day['contributionCount'] > 0:
            streak += 1
            finding_streak = True
        elif finding_streak:
            break
        elif day['date'] < yesterday:
            # If we haven't found a contribution by yesterday, streak is 0
            break
            
    return total_contributions, streak

def update_files(total, streak):
    # Update README.md
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Update shielding badges
    content = re.sub(r'Streak-\d+%2B%20Days', f'Streak-{streak}%2B%20Days', content)
    content = re.sub(r'Contributions-\d+%2B', f'Contributions-{total}%2B', content)
    
    # Update SVG (using simple string replacement for simplicity)
    with open('milestone_stats.svg', 'r', encoding='utf-8') as f:
        svg_content = f.read()
    
    # This assumes the SVG has specific placeholders or we just replace the known values
    # Based on the SVG I created:
    svg_content = re.sub(r'\d+\+ Days', f'{streak}+ Days', svg_content)
    svg_content = re.sub(r'>\d+\+<', f'>{total}+<', svg_content)
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(content)
        
    with open('milestone_stats.svg', 'w', encoding='utf-8') as f:
        f.write(svg_content)

if __name__ == "__main__":
    try:
        total, streak = get_stats()
        # The user mentioned 368+ days, if my calculation is lower due to API limits (usually 1 year),
        # I should allow for a base offset if they specify it, but for now I'll use the real API data.
        # Actually, GitHub GraphQL contributionCalendar covers the last year.
        # If the user has a longer streak, we might need a different approach or just stick to what the API says.
        # I will use the API values.
        update_files(total, streak)
        print(f"Successfully updated stats: {total} contributions, {streak} day streak.")
    except Exception as e:
        print(f"Error: {e}")
