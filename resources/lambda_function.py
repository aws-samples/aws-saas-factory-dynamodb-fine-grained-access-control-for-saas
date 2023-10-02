import json
import random
import boto3
import os
import traceback
import threading
from boto3.dynamodb.conditions import Attr
from enum import Enum

AWS_REGION_NAME = os.environ['AWS_REGION_NAME']
DYNAMO_TABLE_ARN = os.environ['DYNAMO_TABLE_ARN']
DYNAMO_TABLE_NAME = os.environ['DYNAMO_TABLE_NAME']
DYNAMO_ASSUME_ROLE_ARN = os.environ['DYNAMO_ASSUME_ROLE_ARN']

get_all_items_response = []

SUFFIX_START=1
SUFFIX_END=10

class OpStatus(Enum):
    SUCCESSFUL = 'Successful'
    FAILED = 'Failed'

# Default Lambda handler of the function that is the entry point for the REST API calls coming in
def lambda_handler(event, context):
    no_of_test_items_per_call = 3

    # List of Operation definitions supported to be called via the REST API
    def _create_items(tenant_id):
        shard_ids = _create_test_items(tenant_id, no_of_test_items_per_call);
        print("ShardIds :  ", shard_ids)
        return _return_response('Success', 'Items with these Shard Ids created : ' + shard_ids)
    def _get_all_items(tenant_id):
        items = _get_all_items_by_tenantId(tenant_id);
        return _return_response('Success', 'Items : \n' + str(items))
    def _get_item(params):
        response = ''
        op_status = OpStatus.SUCCESSFUL.value
        try:
            item =  _get_item_by_primarykey(params['shard_id'], params['product_id'], params['tenant_id']);
            response = str(item)
        except:
            op_status = OpStatus.FAILED.value
            response = traceback.format_exc()
        finally:
            return _return_response(op_status, '\n' + response)

    # Processing the request, identifying the requested Operation and returning the data
    http_op = event['httpMethod']
    if http_op == "GET":
        params = event['queryStringParameters']
        param_size = len(params)
        if "product_id" in params and "shard_id" in params :
            # if parameter list is tenant_id, product_id & shard_id, then its for get_item
            return _get_item(params)
        elif param_size == 1:
            # if there is one parameter passed in then it's tenant_id, so it's for get_all_items
            return _get_all_items(params['tenant_id'])
        else:
            return _return_response('Not Supported', 'Parameter list is not  supported. Refer the README.md for supported API operations of /items')
    elif http_op == "POST":
        params = json.loads(event['body'])
        return _create_items(params['tenant_id'])
    else:
        return _return_response('Not Supported', 'HTTP operation : "{}" is not yet supported!'.format(http_op))


# The common function that generates the return response
def _return_response(status, msg):
    response = {
        'statusCode': 200,
        'body': '\nOperation ' + status + '. '  + msg + '\n\n'
    }

    return response


# Returns All items belong to a given tenant
def _get_all_items_by_tenantId(tenant_id):
    threads = []
    get_all_items_response.clear()

    for suffix in range(SUFFIX_START, SUFFIX_END + 1):
        partition_id = tenant_id+'-'+str(suffix)
        thread = threading.Thread(target=get_tenant_data, args=[partition_id])
        threads.append(thread)

    # Start threads
    for thread in threads:
        thread.start()
    # Ensure all threads are finished
    for thread in threads:
        thread.join()

    return get_all_items_response

# A thread target. Queries all items by partition_id and assign them in get_all_items_response
def get_tenant_data(partition_id):
    ddb_client = boto3.client('dynamodb')
    response = ddb_client.query(
        TableName=DYNAMO_TABLE_NAME,
        ExpressionAttributeValues={
            ':partition_id': {
                'S': partition_id,
            },
        },
        KeyConditionExpression='ShardID = :partition_id'
    )
    if (len(response.get('Items')) > 0):
        print(response.get('Items'))
        get_all_items_response.append(response.get('Items'))

# Returns the Item specified by the composite primary key which is the combination of shardId and productId
# Needs the tenantID to validate the cross-tenant access
def _get_item_by_primarykey(shardId, productId, tenantID):
    return_val = ""
    table = _get_scoped_ddb_table_by_tenant(tenantID)
    response = table.get_item(
        Key={
            'ShardID': shardId,
            'ProductId' : productId
        }
    )

    if "Item" in response:
        return_val = response['Item']
    else:
        return_val = "But, There is no Item found in the DB for the given input values"

    return return_val


# Saves an item to the DB via a connection scoped by the tenantID with given shardId and productId
def _put_item(table, shard_id, product_id):
    # Get Scoped access to the Dynamo table by TenantID

    item={
        'ShardID': shard_id,
        'ProductId' : product_id,
        'data': _get_sample_product_json()
    }
    response = table.put_item(
        Item = item
    )
    print(item, ' --  ', response)
    return response


# Returns the scoped DDB table connection by given  tenantID
def _get_scoped_ddb_table_by_tenant(tenant_id):
    # Step 01 : Creates the IAM policy document that defines operations that can be performed targeting
    # a tenant specific dataset in the DynamoDB table
    sts_client = boto3.client("sts", region_name=AWS_REGION_NAME)
    assumed_role = sts_client.assume_role(
        RoleArn = DYNAMO_ASSUME_ROLE_ARN,
        RoleSessionName = "tenant-aware-product",
        Policy = _get_policy(tenant_id),
    )
    # Step 02 : Extracts the short-living credentials
    credentials = assumed_role["Credentials"]

    # Step 03 : Creates a scoped DB session that has the access to the dataset belong to given tenant ID
    session = boto3.Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials["SessionToken"],
    )

    # Step 04 : Cretaes the DDB table object from the scoped session that can perform DB operations
    dynamodb = session.resource('dynamodb', region_name=AWS_REGION_NAME)
    table = dynamodb.Table(DYNAMO_TABLE_NAME)

    return table;


# Returns the IAM policy with Tenant Context
def _get_policy(tenant_id):
    policy_template = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:PutItem"
                ],
                "Resource": [
                    DYNAMO_TABLE_ARN
                ],
                "Condition": {
                    "ForAllValues:StringLike": {
                        "dynamodb:LeadingKeys": [
                            "{TENANTID}-*"
                        ]
                    }
                }
            }
        ]
    }
    return json.dumps(policy_template).replace("{TENANTID}", tenant_id)


# Loads 3 random items to the DB for a given tenantID
def _create_test_items(tenant_id, no_of_items):
    shard_ids = []
    table = _get_scoped_ddb_table_by_tenant(tenant_id)
    # Load 3 new items for a given tenantID in the Dynamo Table
    for x in range(0, no_of_items):
        shard_id = tenant_id + '-' + str(_get_shard_suffix())
        shard_ids.append(shard_id)
        _put_item(table, shard_id, _get_product_id())

    return ','.join(shard_ids)

# Returns a sample content to be used as the data of an Item
def _get_sample_product_json():
    return "{sample data}"

# Returns a random value to be used as the Product Id of the items
def _get_product_id():
    return str(_get_random_number(10000, 19999))

# Returns a random value to be used as the post-fix of the ShardId which is = TenantID + "_"+ Post_Fix
def _get_shard_suffix():
    return str(_get_random_number(SUFFIX_START, SUFFIX_END))

# Generates a cryptographically secure random number
def _get_random_number(min, max):
    system_random = random.SystemRandom()
    return str(system_random.randint(min, max))