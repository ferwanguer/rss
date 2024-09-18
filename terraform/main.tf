# Google Cloud Provider Configuration
provider "google" {
  project = "rss-opinion"  # Replace with your project ID                   
  # credentials = file("../rss-opinion-credentials.json")
  region      = "europe-west2"
}

# Create a Google Cloud Storage bucket for storing the RSS feed XML
resource "google_storage_bucket" "rss_feed_bucket" {
  name     = "rss-feed_opinion"    # Replace with a unique bucket name
  location = "EU"

    # Optional: Lifecycle rule example
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
    }
  }
}

# Archive the source code to upload to Cloud Functions
resource "null_resource" "zip_source_code" {
  provisioner "local-exec" {
    command = "cd ../rss-opinion && zip -r ../terraform/function_source.zip *"
  }
  # Ensure the source code archive is created before deploying the Cloud Function
  depends_on = [google_storage_bucket.rss_feed_bucket]

    # Use a trigger to ensure this resource always runs
  triggers = {
    always_run = "${timestamp()}"  # The current timestamp changes on every apply
  }
}

# # Upload the source code archive to Google Cloud Storage
resource "google_storage_bucket_object" "function_source" {
  name   = "${formatdate("YYYYMMDDhhmmss", timestamp())}source.zip"
  bucket = google_storage_bucket.rss_feed_bucket.name
  source = "function_source.zip"

  depends_on = [null_resource.zip_source_code]
  detect_md5hash = true
}


# Create a Google Cloud Function
resource "google_cloudfunctions_function" "check_rss_and_tweet" {
  name        = "checkRssAndTweet"
  runtime     = "python310"
  region      = "europe-west2"
  trigger_http = true
  entry_point = "main"
  max_instances = 200
  


  source_archive_bucket = google_storage_bucket.rss_feed_bucket.name
  source_archive_object = google_storage_bucket_object.function_source.name

  # Environment variables
  # environment_variables = {
  
  # }

  available_memory_mb   = 256   # Set memory allocation as needed
  timeout               = 60    # Set timeout in seconds as needed

  depends_on = [google_storage_bucket_object.function_source]


}

resource "google_cloud_scheduler_job" "http_job" {
  name        = "http-trigger-job"
  description = "Job to trigger the HTTP Cloud Function"
  time_zone = "Europe/Berlin" # Change to your preferred time zone
  schedule    = "0 * * * *" # Running once an hour

  http_target {
    uri          =  var.function_uri 
    http_method  = "GET"
    oidc_token {
      service_account_email = var.service_account 
      audience              = var.function_uri 
    }
    
  }
}

