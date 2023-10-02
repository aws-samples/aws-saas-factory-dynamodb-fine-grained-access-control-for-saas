echo "Current Region is : $AWS_REGION"
printf "Enter the AWS region name you want to deploy the solution below (Just press Enter if it's for us-east-1) : "
read -r region

if [ -z "$region" ]
then
  export AWS_REGION=us-east-1
else
  export AWS_REGION=$region
fi

echo "Region to deploy the solution : $AWS_REGION"

printf "Checking the region to bootstrap the environement..."
ACC_ID=`echo \`aws sts get-caller-identity --query "Account" --output text\``
cdk bootstrap "$ACC_ID/$AWS_REGION"

# Clearn install of the CKD project resources
printf "\nClearning the local workshopace to build the solution..."

rm -rf cdk.out/
rm -rf node_modules/
rm package-lock.json
npm install

# Build the Cloudformation scripts and and deploy the AWS components on the AWS Account
cdk ls; cdk synth; cdk deploy;
