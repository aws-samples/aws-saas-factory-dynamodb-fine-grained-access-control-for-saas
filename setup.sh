echo "\nCleaning the local workspace and building the solution..."
rm -rf cdk.out/
rm -rf node_modules/
rm package-lock.json
npm install

echo "Your current Region is : $AWS_REGION"
printf "Enter the AWS region name you want to deploy the solution (Just press Enter if it's for \"$AWS_REGION\") : "
read -r region

if [ -n "$region" ]
then
  export AWS_REGION=$region
fi

echo "Region to deploy the solution : $AWS_REGION"

printf "Bootstrapping the environment to run CDK app..."
ACC_ID=`echo \`aws sts get-caller-identity --query "Account" --output text\``
cdk bootstrap "aws://$ACC_ID/$AWS_REGION"

# Build the Cloudformation scripts and and deploy the AWS components on the AWS Account
cdk ls; cdk synth; cdk deploy;
