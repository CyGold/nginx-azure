variable "subscription_id" {
    description = "Azure Subscription ID"
    
}
variable "admin_username" { 
    default = "azureuser"
      }
variable "ssh_public_key_path" { 
    default = "~/.ssh/id_rsa.pub" 
    }