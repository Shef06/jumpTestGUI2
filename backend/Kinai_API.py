import requests
from typing import Optional, Dict, List
import json

class KinAPI:
    def __init__(self, base_url: str = "http://localhost:5173"):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL of the API (default: http://localhost:5173)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.authenticated = False
    
    def login(self, email: str, password: str) -> Dict:
        """
        Login to the API and establish a session.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Dictionary containing login response with user data or error
            
        Example:
            >>> api = KinAPI()
            >>> result = api.login("rossi@kin.ai", "password")
            >>> if "error" not in result:
            ...     print(f"Logged in as: {result['user']['email']}")
        """
        url = f"{self.base_url}/api/auth/login"
        
        payload = {
            "email": email,
            "password": password
        }
        
        try:
            response = self.session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.authenticated = True
                    return {"success": True, "user": data.get("user")}
                else:
                    return {"error": "Login failed: Unknown error"}
            else:
                error_data = response.json() if response.text else {}
                return {"error": error_data.get("error", f"HTTP {response.status_code}")}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
    
    def get_all_players(self) -> Dict:
        """
        Fetch all players.
        
        Returns:
            Dictionary containing list of players or error
            
        Example:
            >>> result = api.get_all_players()
            >>> if "data" in result:
            ...     for player in result["data"]:
            ...         print(f"Player ID: {player['id']}")
        """
        if not self.authenticated:
            return {"error": "Not authenticated. Please login first."}
        
        url = f"{self.base_url}/api/players"
        
        try:
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return {"data": data.get("data", [])}
            elif response.status_code == 401:
                self.authenticated = False
                return {"error": "Unauthorized. Session expired. Please login again."}
            else:
                error_data = response.json() if response.text else {}
                return {"error": error_data.get("error", f"HTTP {response.status_code}")}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
    
    def get_player(self, player_id: int) -> Dict:
        """
        Fetch a specific player by ID.
        
        Args:
            player_id: The ID of the player to fetch
            
        Returns:
            Dictionary containing player data or error
            
        Example:
            >>> result = api.get_player(1)
            >>> if "data" in result:
            ...     player = result["data"]
            ...     print(f"Player: {player['info']}")
        """
        if not self.authenticated:
            return {"error": "Not authenticated. Please login first."}
        
        url = f"{self.base_url}/api/players/{player_id}"
        
        try:
            response = self.session.get(url)
            
            if response.status_code == 200:
                data = response.json()
                return {"data": data.get("data")}
            elif response.status_code == 401:
                self.authenticated = False
                return {"error": "Unauthorized. Session expired. Please login again."}
            elif response.status_code == 404:
                return {"error": f"Player with ID {player_id} not found"}
            else:
                error_data = response.json() if response.text else {}
                return {"error": error_data.get("error", f"HTTP {response.status_code}")}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
    
    def logout(self) -> Dict:
        """
        Logout from the API.
        
        Returns:
            Dictionary with success or error message
        """
        if not self.authenticated:
            return {"error": "Not authenticated"}
        
        url = f"{self.base_url}/api/auth/logout"
        
        try:
            response = self.session.post(url)
            
            if response.status_code == 200:
                self.authenticated = False
                return {"success": True}
            else:
                return {"error": f"Logout failed: HTTP {response.status_code}"}
                
        except requests.exceptions.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}


# Example usage
if __name__ == "__main__":
    # Initialize API client
    api = KinAPI("http://localhost:5173")
    
    # Login
    print("Logging in...")
    login_result = api.login("rossi@kin.ai", "password")
    
    if "error" in login_result:
        print(f"Login failed: {login_result['error']}")
        exit(1)
    
    print(f"✓ Logged in as: {login_result['user']['email']}")
    print(f"  User ID: {login_result['user']['id']}")
    print(f"  User Type: {login_result['user']['userType']}")
    print()
    
    # Fetch all players
    print("Fetching all players...")
    players_result = api.get_all_players()
    
    if "error" in players_result:
        print(f"Error fetching players: {players_result['error']}")
    else:
        players = players_result["data"]
        print(f"✓ Found {len(players)} players:")
        for player in players:
            print(f"  - Player ID: {player['id']}")
            if 'info' in player and player['info']:
                print(f"    Info: {json.dumps(player['info'], indent=4)}")
        print()
    
    # Fetch specific player (example with first player ID)
    if players_result.get("data"):
        first_player_id = players_result["data"][0]["id"]
        print(f"Fetching player {first_player_id}...")
        player_result = api.get_player(first_player_id)
        
        if "error" in player_result:
            print(f"Error: {player_result['error']}")
        else:
            player = player_result["data"]
            print(f"✓ Player data:")
            print(json.dumps(player, indent=2))