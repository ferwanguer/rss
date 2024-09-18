terraform {
  backend "gcs" {
    bucket  = "rss-feed_opinion"
    prefix  = "terraform/state"
    # credentials = "../rss-opinion-credentials.json"
  }
}
