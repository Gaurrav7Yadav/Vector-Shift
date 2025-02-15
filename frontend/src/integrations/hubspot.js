import axios from 'axios';

class HubSpotIntegration {
  constructor() {
    this.baseUrl = process.env.REACT_APP_API_URL || 'http://localhost:5000';
  }

  async authorize() {
    try {
      const response = await axios.get(`${this.baseUrl}/authorize_hubspot`);
      // Redirect to HubSpot authorization page
      window.location.href = response.data.authorization_url;
    } catch (error) {
      console.error('Error authorizing HubSpot:', error);
      throw error;
    }
  }

  async getCredentials() {
    try {
      const response = await axios.get(`${this.baseUrl}/get_hubspot_credentials`);
      return response.data;
    } catch (error) {
      console.error('Error getting HubSpot credentials:', error);
      throw error;
    }
  }

  async isAuthenticated() {
    try {
      const credentials = await this.getCredentials();
      return credentials && credentials.access_token;
    } catch (error) {
      return false;
    }
  }
}

export default new HubSpotIntegration(); 