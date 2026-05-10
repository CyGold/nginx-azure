output "nginx_public_ip" {
  value = azurerm_public_ip.nginx.ip_address
}

output "app1_private_ip" {
  value = azurerm_network_interface.app1.private_ip_address
}

output "app2_private_ip" {
  value = azurerm_network_interface.app2.private_ip_address
}