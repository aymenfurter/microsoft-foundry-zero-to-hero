// Lab 7a: Built-in Tools - Spoke Infrastructure
// Creates an AI Foundry project with LOCAL model deployment for built-in tools
@description('Principal ID of the deployer for RBAC assignments')
param deployerPrincipalId string

@description('Local model for built-in tools (Code Interpreter, File Search)')
param localModelName string = 'gpt-4o-mini'

@description('Location for resources')
param location string = resourceGroup().location

// Use subscription ID + RG ID for uniqueness across different users/subscriptions
var uniqueSuffix = uniqueString(subscription().subscriptionId, resourceGroup().id)
var accountName = 'ai-builtin-${uniqueSuffix}'
var projectName = 'builtin-tools-lab'

// AI Services Account (Foundry Hub equivalent)
resource aiAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// AI Foundry Project
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiAccount
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Built-in Tools Lab - Code Interpreter and File Search'
    displayName: 'Built-in Tools Project'
  }
}

// Local model deployment for built-in tools
// Code Interpreter and File Search REQUIRE native deployments (cannot use APIM gateway)
resource localModel 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiAccount
  name: localModelName
  sku: { name: 'GlobalStandard', capacity: 50 }
  properties: {
    model: { name: localModelName, format: 'OpenAI', version: '2024-07-18' }
  }
}

// RBAC: Cognitive Services User for deployer
resource cognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, deployerPrincipalId, 'CognitiveServicesUser')
  scope: aiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// RBAC: Cognitive Services Contributor for deployer
resource cognitiveServicesContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, deployerPrincipalId, 'CognitiveServicesContributor')
  scope: aiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68')
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// Outputs
output accountName string = aiAccount.name
output projectName string = project.name
output projectEndpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'
output modelDeploymentName string = localModel.name
