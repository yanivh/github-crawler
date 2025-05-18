locals {

  s3_script_base_path = "s3://${var.default_s3_bucket}"

  glue_temp_dir = "s3://${var.default_s3_bucket}/etl-artifacts/temp/"

}