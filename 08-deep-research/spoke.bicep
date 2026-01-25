// Spoke deployment for Deep Research Lab
// Deploys:
// - o3-deep-research model in the Landing Zone hub
// - Azure AI Search for Foundry IQ knowledge bases
// - Required RBAC permissions

targetScope = 'resourceGroup'

param location string = resourceGroup().location
param deployerPrincipalId string

// Landing Zone parameters (from Lab 1a)
param hubResourceGroup string
param hubAccountName string
param apimName string

var suffix = substring(uniqueString(resourceGroup().id), 0, 6)
var searchName = 'search-dr-${suffix}'

// Reference to existing Landing Zone hub
resource hubAccount 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: hubAccountName
  scope: resourceGroup(hubResourceGroup)
}

// Deploy o3-deep-research model in the hub (via module for cross-RG deployment)
module deepResearchModel 'deep-research-model.bicep' = {
  name: 'deploy-deep-research-model'
  scope: resourceGroup(hubResourceGroup)
  params: {
    hubAccountName: hubAccountName
  }
}

// Azure AI Search for Foundry IQ
resource search 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchName
  location: location
  sku: { name: 'basic' }
  identity: { type: 'SystemAssigned' }
  properties: {
    hostingMode: 'default'
    partitionCount: 1
    replicaCount: 1
    semanticSearch: 'standard'
  }
}

// Grant deployer Search Index Data Contributor
resource deployerSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'SearchIndexDataContributor')
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7') // Search Index Data Contributor
  }
}

// Grant deployer Search Service Contributor  
resource deployerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, deployerPrincipalId, 'SearchServiceContributor')
  scope: search
  properties: {
    principalId: deployerPrincipalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0') // Search Service Contributor
  }
}

// Add Responses API operation to APIM for Deep Research
module apimResponsesApi 'apim-responses-api.bicep' = {
  name: 'add-responses-api'
  scope: resourceGroup(hubResourceGroup)
  params: {
    apimName: apimName
  }
}

output searchEndpoint string = 'https://${search.name}.search.windows.net'
output searchName string = search.name
output deepResearchModel string = deepResearchModel.outputs.modelName
